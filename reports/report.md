cd $HOME\OneDrive\Desktop\sod-project
git status# IAM Governance & SoD Audit - Simulated ERP

## 1. Scope and method
- Population: 20 users, 11 roles, 11 permissions, 10 SoD rules (simulated ERP export).
- Method: users -> roles -> effective permissions; each user's combined permissions are matched
  against the SoD rule matrix; risk score = impact x likelihood (1-25).
- Levels: CRITICAL >= 20, HIGH 15-19, MEDIUM 10-14, LOW < 10.

## 2. Results
| Metric | Value |
|---|---|
| Users with at least one conflict | 9 of 20 (45%) |
| Total conflicts | 14 |
| CRITICAL / HIGH / MEDIUM / LOW | 1 / 8 / 4 / 1 |
| Caused by role combination | 12 |
| Caused by role design (one role contains both sides) | 2 |

Highest risks:
1. **Ines (R08, score 20)**: VENDOR_MASTER + TREASURY. Can change bank details and execute the payment.
   Also triggers R02 (create vendor + execute payment).
2. **Youssef (R03, 16)**: BUYER + PO_APPROVER. Can approve own purchase orders.
3. **Yasmine (4 conflicts)**: mover-type accumulation, AP_CLERK + SUPER_FINANCE. Worst user overall.
4. **Walid, Yasmine (R06, 15)**: SUPER_FINANCE alone approves and executes payments. This is a
   role design flaw, not a user error.

## 3. Root causes
- **Role design**: SUPER_FINANCE bundles two incompatible duties. Fixing the role fixes it for everyone.
- **Role accumulation**: 7 of 9 conflicted users hold two roles that are safe alone but not together.
- **Privileged access**: IT_ADMIN combined with business roles (Amine, Fares).
- **Not a finding**: Meriem and Zied receive CREATE_VENDOR from two roles. Duplicate permission,
  no conflict. The engine counts permissions as a set, so they are correctly not flagged.

## 4. Remediation (verified)
See `remediation_plan.csv`. Applying it and re-running the audit gives **0 conflicts**.
- Retire SUPER_FINANCE (replaced by the single-purpose AP_MANAGER).
- Remove one role from 8 users, choosing the smallest change that clears every conflict.
- The choice between roles is mechanical (fewest permissions lost). The business owner must confirm
  which duty each person actually needs; `alternatives_considered` lists the other valid options.
- Where a conflict cannot be removed (small team), apply the compensating controls in
  `compensating_controls.csv`.

## 5. Framework mapping
| Control | Where it applies in this project |
|---|---|
| ISO 27001:2022 A.5.3 Segregation of duties | SoD rule matrix and detection |
| ISO 27001:2022 A.5.15 Access control, A.5.18 Access rights | Role model, provisioning, periodic review |
| ISO 27001:2022 A.8.2 Privileged access rights | IT_ADMIN conflicts (R09, R10) |
| NIST SP 800-53 AC-5 Separation of duties | Rule matrix |
| NIST SP 800-53 AC-6 Least privilege | Role removal, role redesign |
| NIST SP 800-53 AC-2 Account management | Joiner/mover/leaver process below |

## 6. Recommended IAM process
1. **Joiner**: access request with manager approval, role assigned from a catalog, SoD check *before* granting.
2. **Mover**: old roles removed when the person changes department (the main cause of accumulation here).
3. **Leaver**: access disabled on the last working day.
4. **Quarterly recertification**: managers confirm each person's roles; privileged roles reviewed more often.
5. **Continuous monitoring**: run `sod_check.py` on every ERP export; alert on any new conflict.

## 7. Limits of this study
Data is simulated and the rule set is small (10 rules). Real SAP/Oracle environments need hundreds of
rules at transaction/authorization-object level, and conflicts depend on organizational scope
(company code, plant). The method transfers; the data volume does not.
