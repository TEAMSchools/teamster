# Cube Security Redesign — Handoff (2026-06-25)

**Branch:** `cristinabaldor/feat/claude-cube-security-redesign` (not yet a PR)
**Issue:** [#4102](https://github.com/TEAMSchools/teamster/issues/4102)
(redesign), [#4092](https://github.com/TEAMSchools/teamster/issues/4092)
(reporting-chain gate),
[#4260](https://github.com/TEAMSchools/teamster/issues/4260) (data-quality deny
population) **Spec (authoritative — read first):**
[`docs/superpowers/specs/2026-06-03-cube-security-redesign.md`](../specs/2026-06-03-cube-security-redesign.md)
(revision 2026-06-24c) **Plan:**
[`docs/superpowers/plans/2026-06-24-cube-security-two-scope-implementation.md`](2026-06-24-cube-security-two-scope-implementation.md)
— ⚠️ its per-task bodies for Tasks **4, 6, 7** still describe an earlier model
(org-gate / summary scopes / `detail` naming). **The spec governs; regenerate
those task briefs from the spec before executing.**

This supersedes `2026-06-24-cube-security-implementation-status.md` (the
original single-scope handoff).

## The model (stable — refold-c)

All Cube access is HR-derived from `dim_staff_cube_access` (keyed on
`staff_key`, resolved by `google_email`) + `dim_staff_reporting_chain`. No
Google Directory API. Key shape:

- **Staff directory + aggregate summary are OPEN** to every staff viewer
  (network-wide). Only **sensitive** staff fields are gated.
- **Sensitive staff fields** (PII now; compensation/observations when those
  cubes exist) are gated by a **shared remit** — `staff_location_scope`
  (network/region/school/none) ∩ `staff_department_scope` (all/own_group/none) —
  plus a **per-field scope enum**: `none` / `all_in_scope` /
  `reporting_chain_or_below_rank` / `reporting_chain` / `teaching_staff`. The
  remit constrains rows **only when a sensitive field is queried**.
- **`reporting_chain`** = everyone who reports up to you (direct + indirect,
  from `dim_staff_reporting_chain`), unbounded by location/department. The
  single term for that concept; never means same-level peers.
- **Students** keep `student_summary_location_scope` /
  `student_detail_location_scope` / `student_pii_scope` (no directory split,
  inherently sensitive).
- **Multi-sensitive-field queries intersect** (most-restrictive wins).

See the spec for the full table of scope semantics and the `queryRewrite`
composition.

## Done and committed (dbt layer complete + validated)

| Commit    | Contents                                                           |
| --------- | ------------------------------------------------------------------ |
| `c64f106` | Task 1 — two-scope crosswalk source schema + staging contracts     |
| `d7a00fc` | Task 2 — `dim_staff_cube_access` reworked to the refold-c columns  |
| (earlier) | Task 8 — `tests/cube/test_cube_schema.py` (no `dim_`/`fct_` names) |
| (earlier) | spec revisions (24a/b/c), plan, CSVs                               |

**Validation done:**

- Sheets filled by the user and staged
  (`stage_external_sources --target staging`, `ext_full_refresh: true`).
- `stg_google_sheets__people__cube_access_{role,department_override,department_rollup}`
  built `--target staging` → 26 tests pass (contracts match the sheet; all enum
  `accepted_values` pass).
- `dim_staff_cube_access` built `--target staging` → 21 tests pass: 1:1 on
  `staff_key`, FK to `dim_staff`, all `accepted_values`.
- Aggregate sanity (zz_stg): **1,496** staff; **59** full-deny (the #4260
  population); **137** with `reporting_chain_or_below_rank` observations; **0**
  with `teaching_staff` PII (no active `ASL`-coded staff today — flag to data
  team if ASLs are expected).

`dim_staff_reporting_chain` is unchanged from the original build (still valid).

## Remaining work (Cube layer — all code-writable, no sheet dependency)

Execute in this order; details in the spec's "Changes required" /
"Implementation sequence". Validate locally as noted; only Task 10 needs Cube
Cloud.

1. **Task 3 — `staff` cube join.** Convert
   `src/cube/model/cubes/staff/staff.yml` from
   `sql_table: kipptaf_marts.dim_staff` to inline `sql:` that `LEFT JOIN`s
   `kipptaf_marts.dim_staff_cube_access` on `staff_key`, exposing **only**
   `job_function_level`, `job_function_code`, `department_group` (the
   viewee-side filter members; never the access-policy columns). Add the three
   dimensions.
2. **Task 4 — staff views.** `staff_detail`: rename the access tier to
   `cube-access-staff-directory` (`includes: "*"`, `excludes:` the six sensitive
   fields — `personal_email`, `personal_cell_phone`, `birth_date`,
   `gender_identity`, `race`, `is_hispanic`) + keep `cube-access-staff-pii`
   (`includes: "*"`); expose `staff_key`, `job_function_level`,
   `job_function_code`, `department_group` as members for the row filters.
   `staff_summary`: single open tier (`cube-access-staff-directory`).
3. **Task 5 — student views (6 files).** Rename `cube-access-student-data` →
   `cube-access-student-detail` on the 3 detail views (keep `-pii`) and →
   `cube-access-student-summary` on the 3 summary views.
4. **Task 6 — rework `src/cube/access.js`.** ⚠️ The committed `access.js`
   (`3b06b542f`) encodes the OLD org-gate model and must be rewritten. New
   shape: `buildGroups` emits `cube-access-staff-directory` for every staff
   viewer + `cube-access-staff-pii` when `staff_pii_scope != none` (and student
   `-detail`/`-summary`/`-pii` per the student scopes); per-field sensitive row
   filters (each enum value → its filter; intersection across requested
   sensitive fields); `isStaffMember`. Keep it pure + unit-tested
   (`node --test src/cube/access.test.js`).
5. **Task 7 — `cube.js`.** Replace Directory API with two BigQuery reads
   (`dim_staff_cube_access` by `google_email`; `dim_staff_reporting_chain` by
   `manager_staff_key`), cached to midnight ET. `queryRewrite`: directory-only
   staff query → no filter; sensitive staff field → per-field scope
   intersection; student → location filter by surface; preserve the
   snapshot-anchor guard and `canSwitchSqlUser`. Validate it loads:
   `node -e "require('./src/cube/cube.js')"`.
6. **Task 9 — docs.** Update `src/cube/CLAUDE.md` security-model + view-policy
   sections and the staff view YAML descriptions (the #4092 gate).
7. **Task 10 — Dev Mode validation (USER env).** Push branch; in Cube Cloud Dev
   Mode validate per tier: directory open to all; sensitive fields scoped;
   `reporting_chain` vs `reporting_chain_or_below_rank` vs `all_in_scope`;
   `teaching_staff` = school teachers; KTAF central-office sees below-rank evals
   in their department group; no-access viewer denied. Confirm
   `GOOGLE_DIRECTORY_*` secrets are no longer required.

After live + validated: retire the `cube-*` Google Workspace groups (now
internal names) and close out #4260.

## How to resume — commands that worked

- **Merge main first**, then read the spec + this doc.
- **Prod manifest for `--defer`** (regenerate if stale; not blocked):
  `uv run dbt parse --target prod --target-path target/prod --project-dir src/dbt/kipptaf`
- **Re-validate the dbt layer** (the working build invocation):
  `uv run dbt build --select dim_work_assignment_jobs stg_google_sheets__people__cube_access_department_rollup dim_staff_cube_access --target staging --defer --state target/prod --project-dir src/dbt/kipptaf`
  — `--state` is **relative to `--project-dir`** (use `target/prod`, not the
  repo-root path). `dim_work_assignment_jobs` **must be in `--select`**: prod
  lacks the branch's `job_function_code`, so deferring it to prod fails with
  "Name job_function_code not found inside j".
- **Re-stage the sheets** only if the `zz_stg` externals get reset:
  `uv run dbt run-operation stage_external_sources --args 'select: google_sheets.src_google_sheets__people__cube_access_role google_sheets.src_google_sheets__people__cube_access_department_override' --vars '{ext_full_refresh: true}' --target staging --project-dir src/dbt/kipptaf`
  (needs `ext_full_refresh: true`; classifier-gated — run in a user terminal).
- **Aggregate checks on the built dim**: use the **BigQuery MCP**
  (`mcp__bigquery__execute_sql` against
  `zz_stg_kipptaf_marts.dim_staff_cube_access`). The `bq` CLI has no active
  account in this Codespace; the MCP uses ADC.
- The crosswalk CSVs were delivered to the session scratchpad (ephemeral). The
  **live source of truth is the Google Sheet** (already filled + staged); CSV
  content is reproducible from the spec's role table if ever needed.

## Open items for the data team / user decisions

- **`teaching_staff` resolves to 0 staff** — no active+primary `ASL`-coded staff
  in current data. Confirm whether ASLs should exist.
- **#4260 deny population** — 59 active+primary staff resolve to full-deny (NULL
  job-function / unmatched role). Aggregate only; no PII. Still tracked.
- **MGDIR department scope (undecided):** the KTAF `MGDIR` rows carry
  `staff_department_scope = all`, so their `reporting_chain_or_below_rank`
  observation scope is network-wide-below-rank (all departments), not bounded to
  a department group like `DIR`/`KTRGS` (`own_group`). Decide whether MGDIR
  should be `own_group`.
- **Central-office comp/PII broadening (undecided):** only
  `staff_observations_scope` was broadened to `reporting_chain_or_below_rank`
  for the KTAF central office; `staff_compensation_scope` / `staff_pii_scope`
  stayed `reporting_chain`. Decide whether comp/PII should follow.
