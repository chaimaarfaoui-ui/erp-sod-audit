"""Step 4 - check ONE user against every SoD rule, printing each check."""
import pandas as pd

users = pd.read_csv("data/users.csv", dtype=str)
roles = pd.read_csv("data/roles.csv", dtype=str)
rules = pd.read_csv("data/sod_rules.csv")

access = users.merge(roles, on="role", how="left")

NAME = "Karim"   # try "Omar", "Yasmine", "Meriem", "Sara" afterwards

mine = access[access["name"] == NAME]
perms = set(mine["permission"])
print(f"{NAME}'s permissions: {sorted(perms)}\n")

hits = 0
for rule in rules.itertuples(index=False):
    has_a = rule.perm_a in perms
    has_b = rule.perm_b in perms
    status = "CONFLICT" if (has_a and has_b) else "ok"
    print(f"{rule.rule_id}: {rule.perm_a:<21} {has_a!s:<5} + {rule.perm_b:<17} {has_b!s:<5} -> {status}")
    if has_a and has_b:
        hits += 1
        print(
            f"     score = {rule.impact} x {rule.likelihood} = {rule.impact * rule.likelihood}")

print(f"\n{NAME}: {hits} conflict(s)")
