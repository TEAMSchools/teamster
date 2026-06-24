# Cube Security Two-Scope — SDD Progress Ledger

Plan:
docs/superpowers/plans/2026-06-24-cube-security-two-scope-implementation.md
Branch: cristinabaldor/feat/claude-cube-security-redesign

## Status

Executing no-prerequisite tasks first (6, 8). Tasks 1-2 dbt-build validation
blocks on the data team updating the crosswalk sheet + re-staging (see plan
Prerequisites). Tasks 3-5, 7 are code-writable now; full runtime validation
(Task 10) needs Cube Dev Mode (user env).

## Design refold (2026-06-24b) — affects open tasks

Spec refolded (24c): staff directory AND summary open (no staff*summary*_ / no
staff*detail*_ "detail" naming). Sensitive fields gated by a shared remit
(staff_location_scope + staff_department_scope) + per-field enum (none/
all_in_scope/reporting_chain_or_below_rank/reporting_chain/teaching_staff). Term
"reporting_chain" (aligned with dim_staff_reporting_chain). Remit limits rows
ONLY when a sensitive field is queried. Students keep summary+detail location
scopes + student_pii_scope. => Task 6 access.js (3b06b542f) now encodes the OLD
model — SUPERSEDED, rework on resume against the revised spec. Tasks 1,2,4,7
also regenerate. Task 8 unaffected.

## Completed

Task 6: SUPERSEDED by refold (commit 3b06b54 was clean for the OLD model;
rework) Task 8: complete (commit 1313031, review clean — Spec ✅, quality
Approved)

## Minor findings (for final whole-branch review triage)

- Task 6: `staffColumnNarrowing` reporting_chain + empty-downline → DENY_FILTER
  is correct but untested.
- Task 6: `own_group` department path in `staffDetailFilters` has no test.
- Task 6: trunk/lint not run on the new `.js` files (pre-commit fmt may have
  run; confirm at CI).
