# Cube Security Two-Scope — SDD Progress Ledger

Plan:
docs/superpowers/plans/2026-06-24-cube-security-two-scope-implementation.md
Spec: docs/superpowers/specs/2026-06-03-cube-security-redesign.md (refold 24c)
Branch: cristinabaldor/feat/claude-cube-security-redesign

## Model (stable, refold-c)

Staff directory + summary OPEN. Sensitive fields gated by shared remit
(staff_location_scope + staff_department_scope) + per-field enum (none /
all_in_scope / reporting_chain_or_below_rank / reporting_chain /
teaching_staff). Term "reporting_chain". Students keep summary + detail location
scopes + pii.

## Completed

- Task 1: crosswalk source schema + staging contracts — committed c64f106.
  Sheets staged (--target staging); staging models built + 26 tests PASS.
- Task 2: dim_staff_cube_access reworked — committed d7a00fc37. Built --target
  staging (defer + dim_work_assignment_jobs for the branch job_function_code);
  21 tests PASS (1:1 on staff_key, FK ok, accepted_values ok). Sanity: 1496
  staff, 59 full-deny (#4260), 137 obs reporting_chain_or_below_rank, 0 pii
  teaching_staff (no active ASL-coded staff — flag to data team).
- Task 8: tests/cube/test_cube_schema.py — committed 1313031.

## Remaining (Cube layer — plan tasks need refold-c regeneration before run)

- Task 3: staff cube inline join (job_function_level / job_function_code /
  department_group).
- Task 4: staff views — staff_detail: cube-access-staff-directory + -pii, expose
  the 3 filter members; staff_summary: single open tier.
- Task 5: student views rename to -detail / -summary / -pii (6 files).
- Task 6: REWORK access.js (committed 3b06b542f encodes OLD org_gate model) for
  open-directory + per-field reporting_chain scopes.
- Task 7: cube.js — BigQuery contextToGroups + open-directory queryRewrite.
- Task 9: docs (src/cube/CLAUDE.md + staff view yaml).
- Task 10: Dev Mode validation (user env).
