"""Step 2 - look at the three input tables."""
import pandas as pd

users = pd.read_csv("data/users.csv", dtype=str)
roles = pd.read_csv("data/roles.csv", dtype=str)
rules = pd.read_csv("data/sod_rules.csv")

print("USERS: rows, columns ->", users.shape)
print(users.head(5).to_string(index=False))

print("\nROLES: rows, columns ->", roles.shape)
print(roles.head(5).to_string(index=False))

print("\nRULES: rows, columns ->", rules.shape)
print(rules[["rule_id", "perm_a", "perm_b"]].head(3).to_string(index=False))

print("\nDistinct users :", users["user_id"].nunique())
print("Distinct roles :", roles["role"].nunique())
print("Distinct perms :", roles["permission"].nunique())

print("\nRoles per user (top 3):")
print(users.groupby("name")["role"].count().sort_values(
    ascending=False).head(3).to_string())
