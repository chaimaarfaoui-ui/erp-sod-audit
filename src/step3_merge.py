"""Step 3 - expand users -> roles -> permissions with a merge."""
import pandas as pd

users = pd.read_csv("data/users.csv", dtype=str)
roles = pd.read_csv("data/roles.csv", dtype=str)

access = users.merge(roles, on="role", how="left")

print("users rows :", len(users))
print("access rows:", len(access))

print("\nKarim's access (one row per role + permission):")
print(access[access["name"] == "Karim"]
      [["name", "role", "permission"]].to_string(index=False))

print("\nMeriem's access (note CREATE_VENDOR twice):")
print(access[access["name"] == "Meriem"]
      [["name", "role", "permission"]].to_string(index=False))

print("\nMeriem, after removing duplicates with a set:")
print(sorted(set(access[access["name"] == "Meriem"]["permission"])))

print("\nRows with a missing permission (should be 0):",
      access["permission"].isna().sum())
