"""Step 6 - apply fixes by hand, then PROVE them by re-running the detection."""
import pandas as pd

users = pd.read_csv("data/users.csv", dtype=str)
roles = pd.read_csv("data/roles.csv", dtype=str)
rules = pd.read_csv("data/sod_rules.csv")


def detect(user_rows):
    """Return the set of (name, rule_id) conflicts for a users table."""
    access = user_rows.merge(roles, on="role", how="left")
    found = set()
    for name, group in access.groupby("name"):
        perms = set(group["permission"])
        for rule in rules.itertuples(index=False):
            if rule.perm_a in perms and rule.perm_b in perms:
                found.add((name, rule.rule_id))
    return found


def remove_roles(user_rows, removals):
    """removals = {"Karim": ["AP_MANAGER"], ...} -> users table without those rows."""
    drop = [(n, r) for n, rs in removals.items() for r in rs]
    keep = [(n, r) not in drop for n, r in zip(
        user_rows["name"], user_rows["role"])]
    return user_rows[keep].reset_index(drop=True)


def replace_role(user_rows, old, new):
    out = user_rows.copy()
    out["role"] = out["role"].replace(old, new)
    return out.drop_duplicates().reset_index(drop=True)


before = detect(users)
print(f"BEFORE            : {len(before)} conflicts")

# ---- Attempt 1: naive. Remove one role from each person with two roles ----
naive = {"Karim": ["AP_MANAGER"], "Omar": ["WAREHOUSE"], "Youssef": ["PO_APPROVER"],
         "Ines": ["TREASURY"], "Tarek": ["FINANCE_CONTROLLER"], "Amine": ["GL_ACCOUNTANT"],
         "Fares": ["AP_MANAGER"], "Yasmine": ["AP_CLERK"]}
after1 = detect(remove_roles(users, naive))
print(
    f"AFTER ATTEMPT 1   : {len(after1)} conflicts  -> still open: {sorted(after1)}")

# ---- Attempt 2: fix the role design first, then remove the extra roles ----
step_a = replace_role(users, "SUPER_FINANCE",
                      "AP_MANAGER")      # retire the bad role
print(f"  after redesign  : {len(detect(step_a))} conflicts")
plan = {"Karim": ["AP_MANAGER"], "Omar": ["WAREHOUSE"], "Youssef": ["PO_APPROVER"],
        "Ines": ["TREASURY"], "Tarek": ["FINANCE_CONTROLLER"], "Amine": ["GL_ACCOUNTANT"],
        "Fares": ["AP_MANAGER"], "Yasmine": ["AP_MANAGER"]}
fixed = remove_roles(step_a, plan)
after2 = detect(fixed)
print(f"AFTER ATTEMPT 2   : {len(after2)} conflicts")

# ---- What did each person lose? (the business cost of the fix) ----
print("\nPermissions lost per user:")
old_perms = users.merge(roles, on="role").groupby("name")[
    "permission"].agg(set)
new_perms = fixed.merge(roles, on="role").groupby("name")[
    "permission"].agg(set)
for name in sorted(plan.keys() | {"Walid"}):
    lost = sorted(old_perms[name] - new_perms[name])
    print(f"  {name:<8} {lost if lost else '-'}")

print("\nVERIFIED: no conflict remains." if not after2 else "\nWARNING: conflicts remain!")
