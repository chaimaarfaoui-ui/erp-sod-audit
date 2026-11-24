"""Step 5 - run the SoD check for ALL users, add risk levels, cross-check the engine."""
import pandas as pd

users = pd.read_csv("data/users.csv", dtype=str)
roles = pd.read_csv("data/roles.csv", dtype=str)
rules = pd.read_csv("data/sod_rules.csv")

access = users.merge(roles, on="role", how="left")


def risk_level(score):
    if score >= 20:
        return "CRITICAL"
    if score >= 15:
        return "HIGH"
    if score >= 10:
        return "MEDIUM"
    return "LOW"


findings = []
for name, group in access.groupby("name"):
    perms = set(group["permission"])
    for rule in rules.itertuples(index=False):
        if rule.perm_a in perms and rule.perm_b in perms:
            score = rule.impact * rule.likelihood
            findings.append({"name": name, "rule_id": rule.rule_id,
                             "score": score, "level": risk_level(score)})

df = pd.DataFrame(findings).sort_values(["score", "name"], ascending=[False, True])

print(df.to_string(index=False))
print("\nTotal conflicts :", len(df))
print("Users affected  :", df["name"].nunique())
print("\nPer user:")
print(df.groupby("name")["score"].agg(["count", "sum"]).sort_values("sum", ascending=False).to_string())

engine = pd.read_csv("reports/findings.csv")
mine = set(zip(df["name"], df["rule_id"]))
theirs = set(zip(engine["name"], engine["rule_id"]))
print("\nSame result as the engine:", mine == theirs)