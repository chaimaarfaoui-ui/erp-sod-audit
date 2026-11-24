"""
remediation.py - Propose fixes for SoD conflicts, then PROVE they work.

Stage 1  Role redesign : retire badly designed roles (e.g. SUPER_FINANCE)
Stage 2  Role removal  : for each remaining conflicted user, find the smallest
                         set of roles to remove that clears every conflict
Stage 3  Verification  : re-run the audit on the corrected data -> must be 0

Run from the project root (after sod_check.py):
    python src/remediation.py
"""

from itertools import combinations

import pandas as pd

from sod_check import REPORTS, detect_conflicts, expand_access, load_data

# Stage 1 decision. SUPER_FINANCE bundles approve + execute payment, which is
# a conflict by design. Retire it and fall back on the existing single-purpose
# role. (ASSUMPTION for the exercise: holders were approving payments.)
ROLE_REDESIGN = {"SUPER_FINANCE": ["AP_MANAGER"]}

# Where a conflict cannot be removed (small team), these controls compensate.
COMPENSATING_CONTROLS = {
    "R01": "Second person validates every new vendor; monthly new-vendor report reviewed by finance director",
    "R02": "Dual authorization on payments to vendors created in the last 30 days",
    "R03": "Workflow forces approval by a different user; PO value thresholds",
    "R04": "Goods receipt confirmed by warehouse; 3-way match (PO, receipt, invoice)",
    "R05": "Payment run requires approver different from invoice poster; review of exceptions report",
    "R06": "Dual control on payment release; daily bank-limit alerts",
    "R07": "Journal approval workflow blocks self-approval; review of manual journals",
    "R08": "Bank-detail changes verified by call-back; change log reviewed before each payment run",
    "R09": "Admin actions logged to separate system; quarterly privileged-access review",
    "R10": "Admin actions logged to separate system; quarterly privileged-access review",
}


def apply_redesign(users):
    rows = []
    for r in users.itertuples(index=False):
        if r.role in ROLE_REDESIGN:
            for new_role in ROLE_REDESIGN[r.role]:
                rows.append({**r._asdict(), "role": new_role})
        else:
            rows.append(r._asdict())
    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def count_conflicts(user_rows, roles, rules):
    if user_rows.empty:
        return 0
    return len(detect_conflicts(expand_access(user_rows, roles), rules))


def best_removal(user_rows, roles, rules):
    """Smallest role removal that clears all conflicts; ties -> fewest permissions lost."""
    role_list = list(user_rows["role"])
    perms_per_role = roles.groupby("role")["permission"].nunique().to_dict()

    for k in range(1, len(role_list) + 1):
        options = []
        for combo in combinations(role_list, k):
            remaining = user_rows[~user_rows["role"].isin(combo)]
            if count_conflicts(remaining, roles, rules) == 0:
                lost = sum(perms_per_role[r] for r in combo)
                options.append((lost, combo))
        if options:
            options.sort()
            return options[0][1], [o[1] for o in options]
    return None, []


def main():
    users, roles, rules = load_data()
    before = detect_conflicts(expand_access(users, roles), rules)

    # Stage 1
    redesigned = apply_redesign(users)
    roles_after = roles[~roles["role"].isin(ROLE_REDESIGN)]
    roles_after = pd.concat(
        [roles_after, roles[roles["role"].isin(sum(ROLE_REDESIGN.values(), []))]]
    ).drop_duplicates()

    # Stage 2
    plan = []
    corrected = redesigned.copy()
    for user_id, rows in redesigned.groupby("user_id"):
        if count_conflicts(rows, roles_after, rules) == 0:
            continue
        removal, alternatives = best_removal(rows, roles_after, rules)
        name = rows["name"].iloc[0]
        original_roles = sorted(users.loc[users["user_id"] == user_id, "role"])
        plan.append(
            {
                "user_id": user_id,
                "name": name,
                "original_roles": "|".join(original_roles),
                "action": "REMOVE ROLE",
                "roles_removed": "|".join(removal),
                "roles_kept": "|".join(sorted(set(rows["role"]) - set(removal))),
                "alternatives_considered": " / ".join("+".join(a) for a in alternatives),
            }
        )
        corrected = corrected[~((corrected["user_id"] == user_id) & (corrected["role"].isin(removal)))]

    # Record the Stage-1 redesign in the plan for affected users
    for uid in users.loc[users["role"].isin(ROLE_REDESIGN), "user_id"].unique():
        name = users.loc[users["user_id"] == uid, "name"].iloc[0]
        existing = [p for p in plan if p["user_id"] == uid]
        note = "SUPER_FINANCE retired -> AP_MANAGER"
        if existing:
            existing[0]["action"] = f"REDESIGN + {existing[0]['action']}"
            existing[0]["alternatives_considered"] = f"{note}; {existing[0]['alternatives_considered']}"
        else:
            plan.append(
                {
                    "user_id": uid, "name": name,
                    "original_roles": "|".join(sorted(users.loc[users["user_id"] == uid, "role"])),
                    "action": "REDESIGN ROLE",
                    "roles_removed": "SUPER_FINANCE",
                    "roles_kept": "AP_MANAGER",
                    "alternatives_considered": note,
                }
            )

    plan_df = pd.DataFrame(plan).sort_values("user_id").reset_index(drop=True)
    plan_df.to_csv(REPORTS / "remediation_plan.csv", index=False)

    # Stage 3: verification
    after = detect_conflicts(expand_access(corrected, roles_after), rules)
    corrected.to_csv(REPORTS / "users_after_remediation.csv", index=False)

    # Controls to use if a business cannot apply the removal
    ctrl = (
        before.groupby("rule_id")
        .agg(occurrences=("user_id", "count"), risk_score=("risk_score", "max"))
        .reset_index()
    )
    ctrl["compensating_control"] = ctrl["rule_id"].map(COMPENSATING_CONTROLS)
    ctrl.sort_values("risk_score", ascending=False).to_csv(REPORTS / "compensating_controls.csv", index=False)

    print("=" * 60)
    print("REMEDIATION SIMULATION")
    print("=" * 60)
    print(f"Conflicts BEFORE : {len(before)}  ({before['user_id'].nunique()} users)")
    print(f"Conflicts AFTER  : {len(after)}  ({after['user_id'].nunique() if not after.empty else 0} users)")
    print("\nPlan:")
    print(plan_df[["name", "original_roles", "action", "roles_removed", "roles_kept"]].to_string(index=False))
    print("\nVERIFIED: no SoD conflict remains." if after.empty else "\nWARNING: conflicts remain!")


if __name__ == "__main__":
    main()
