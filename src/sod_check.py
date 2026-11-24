"""
sod_check.py - Separation of Duties (SoD) detection engine.

Pipeline:
    users.csv + roles.csv  ->  effective permissions per user
    effective permissions + sod_rules.csv  ->  conflicts
    conflicts -> risk score (impact x likelihood) -> CSV + heatmap

Run from the project root:
    python src/sod_check.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


# --------------------------------------------------------------------------
# 1. Load
# --------------------------------------------------------------------------
def load_data(data_dir=DATA):
    users = pd.read_csv(data_dir / "users.csv", dtype=str)
    roles = pd.read_csv(data_dir / "roles.csv", dtype=str)
    rules = pd.read_csv(data_dir / "sod_rules.csv")
    return users, roles, rules


def validate(users, roles, rules):
    """Fail loudly on data errors. A typo here would silently hide conflicts."""
    unknown_roles = set(users["role"]) - set(roles["role"])
    if unknown_roles:
        raise ValueError(f"Roles in users.csv missing from roles.csv: {sorted(unknown_roles)}")

    known_perms = set(roles["permission"])
    for col in ("perm_a", "perm_b"):
        unknown = set(rules[col]) - known_perms
        if unknown:
            print(f"[warning] {col} has permissions no role grants: {sorted(unknown)}")


# --------------------------------------------------------------------------
# 2. Expand: user -> roles -> permissions
# --------------------------------------------------------------------------
def expand_access(users, roles):
    """One row per (user, role, permission)."""
    return users.merge(roles, on="role", how="left")


# --------------------------------------------------------------------------
# 3. Detect
# --------------------------------------------------------------------------
def risk_level(score):
    if score >= 20:
        return "CRITICAL"
    if score >= 15:
        return "HIGH"
    if score >= 10:
        return "MEDIUM"
    return "LOW"


def detect_conflicts(access, rules):
    """Return one row per (user, violated rule)."""
    findings = []

    for (user_id, name, dept), grp in access.groupby(["user_id", "name", "department"]):
        # permission -> set of roles granting it. A set means a permission
        # granted by 2 roles is counted once (no false positive).
        perm_sources = grp.groupby("permission")["role"].agg(lambda s: sorted(set(s))).to_dict()
        user_perms = set(perm_sources)

        for rule in rules.itertuples(index=False):
            if rule.perm_a in user_perms and rule.perm_b in user_perms:
                roles_a = perm_sources[rule.perm_a]
                roles_b = perm_sources[rule.perm_b]
                # Is there one role that carries both sides of the conflict?
                single_role = sorted(set(roles_a) & set(roles_b))
                score = int(rule.impact) * int(rule.likelihood)
                findings.append(
                    {
                        "user_id": user_id,
                        "name": name,
                        "department": dept,
                        "rule_id": rule.rule_id,
                        "perm_a": rule.perm_a,
                        "perm_b": rule.perm_b,
                        "roles_giving_a": "|".join(roles_a),
                        "roles_giving_b": "|".join(roles_b),
                        "cause": "ROLE DESIGN" if single_role else "ROLE COMBINATION",
                        "risk_description": rule.risk_description,
                        "impact": int(rule.impact),
                        "likelihood": int(rule.likelihood),
                        "risk_score": score,
                        "risk_level": risk_level(score),
                    }
                )

    cols = [
        "user_id", "name", "department", "rule_id", "perm_a", "perm_b",
        "roles_giving_a", "roles_giving_b", "cause", "risk_description",
        "impact", "likelihood", "risk_score", "risk_level",
    ]
    df = pd.DataFrame(findings, columns=cols)
    if not df.empty:
        df = df.sort_values(["risk_score", "user_id"], ascending=[False, True]).reset_index(drop=True)
    return df


def run_audit(data_dir=DATA):
    users, roles, rules = load_data(data_dir)
    validate(users, roles, rules)
    access = expand_access(users, roles)
    return detect_conflicts(access, rules), users, rules


# --------------------------------------------------------------------------
# 4. Reporting helpers
# --------------------------------------------------------------------------
def user_summary(findings, users):
    all_users = users[["user_id", "name", "department"]].drop_duplicates()
    if findings.empty:
        all_users["conflicts"] = 0
        all_users["max_risk"] = 0
        all_users["total_risk"] = 0
        return all_users
    agg = (
        findings.groupby("user_id")
        .agg(conflicts=("rule_id", "count"),
             max_risk=("risk_score", "max"),
             total_risk=("risk_score", "sum"))
        .reset_index()
    )
    out = all_users.merge(agg, on="user_id", how="left").fillna(0)
    out[["conflicts", "max_risk", "total_risk"]] = out[["conflicts", "max_risk", "total_risk"]].astype(int)
    return out.sort_values(["total_risk", "user_id"], ascending=[False, True]).reset_index(drop=True)


def make_heatmap(findings, users, rules, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    people = users[["user_id", "name"]].drop_duplicates().reset_index(drop=True)
    labels_y = [f"{r.name} ({r.user_id})" for r in people.itertuples()]
    labels_x = list(rules["rule_id"])
    grid = np.zeros((len(people), len(rules)))
    for f in findings.itertuples():
        i = people.index[people["user_id"] == f.user_id][0]
        j = labels_x.index(f.rule_id)
        grid[i, j] = f.risk_score

    fig, ax = plt.subplots(figsize=(9, 9))
    masked = np.ma.masked_where(grid == 0, grid)
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad("#f4f4f4")
    im = ax.imshow(masked, cmap=cmap, vmin=5, vmax=25, aspect="auto")
    ax.set_xticks(range(len(labels_x)), labels_x)
    ax.set_yticks(range(len(labels_y)), labels_y)
    ax.xaxis.tick_top()
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if grid[i, j]:
                ax.text(j, i, int(grid[i, j]), ha="center", va="center", fontsize=9, fontweight="bold")
    ax.set_title("SoD risk heatmap: users vs. violated rules (cell = impact x likelihood)", pad=36)
    fig.colorbar(im, ax=ax, label="Risk score", shrink=0.7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    REPORTS.mkdir(exist_ok=True)
    findings, users, rules = run_audit()

    findings.to_csv(REPORTS / "findings.csv", index=False)
    summary = user_summary(findings, users)
    summary.to_csv(REPORTS / "user_summary.csv", index=False)
    make_heatmap(findings, users, rules, REPORTS / "heatmap.png")

    n_users = users["user_id"].nunique()
    n_bad = findings["user_id"].nunique()
    print("=" * 60)
    print("SoD AUDIT RESULT")
    print("=" * 60)
    print(f"Users audited         : {n_users}")
    print(f"Users with conflicts  : {n_bad}")
    print(f"Clean users           : {n_users - n_bad}")
    print(f"Total conflicts       : {len(findings)}")
    print("\nBy risk level:")
    print(findings["risk_level"].value_counts().to_string())
    print("\nBy cause:")
    print(findings["cause"].value_counts().to_string())
    print("\nTop findings:")
    print(findings[["name", "rule_id", "roles_giving_a", "roles_giving_b",
                    "risk_score", "risk_level"]].to_string(index=False))
    print(f"\nFiles written to {REPORTS}")


if __name__ == "__main__":
    main()
