# Cube Security Redesign — HR-Derived Access with Open Directory + Per-Field Scopes

**Issue:** [#4102](https://github.com/TEAMSchools/teamster/issues/4102)
**Branch:** `cristinabaldor/feat/claude-cube-security-redesign`

**Revision history.**

- 2026-06-03 — single `scope_level` capping both summary and detail, boolean-ish
  `*_access_level` tiers.
- 2026-06-24a — decomposed into independent axes (summary vs detail scope per
  domain; location and department split apart).
- 2026-06-24b (this revision) — **staff directory is open**; only _sensitive_
  staff fields are gated. The org-relation gate (`staff_detail_org_gate`) folds
  into a self-contained scope enum on each sensitive field. A single term
  **`reporting_chain`** (aligned with `dim_staff_reporting_chain`) is used for
  "the people who report up to you" — replacing the prior mix of "reporting
  chain" / "downline" / "team". It means strictly your direct + indirect
  reports, never same-level peers. Prior models are in git history.

## Summary

Move all Cube access control into Cube itself, derived from HR data. Two dbt
models are the source of truth, replacing manual Google Workspace group
enrollment and the Google Admin Directory API entirely:

- `dim_staff_cube_access` — one row per active+primary staff member (keyed on
  `staff_key`); resolves each person's **current role** to access scopes via the
  Google Sheets crosswalks.
- `dim_staff_reporting_chain` — the transitive closure of the current org tree
  (manager → every direct/indirect report), keyed on `staff_key`. It is the data
  behind a viewer's **reporting chain** (everyone who reports up to them,
  directly or indirectly).

Identity keys on `staff_key`. The JWT email claim is used in exactly one place —
a boundary lookup resolving email → `staff_key`.

## Access model

### Staff: an open directory, with gated sensitive fields

The staff data splits into two kinds of field, not two row-gated views:

- **Directory / employment fields** (names, work email, AD username, title, job
  function, worker type, department, location, manager, FTE, status, tenure
  dates, org structure) are an **internal directory — open to every staff
  viewer, network-wide, no row gate.** These are not sensitive on their own;
  they only matter in combination with the gated fields below, so gating them
  buys nothing.
- **Sensitive fields** (personal contact, date of birth, demographics; and —
  when those cubes are built — compensation, observations) are **gated per
  field**, by a self-contained scope enum, bounded by a shared staff location +
  department scope.

So there is no "is the staff row visible" gate — the row gate fires **only when
a query touches a sensitive field**, and then only restricts to that field's
scope. A directory-only query returns all staff.

### Students: location-scoped detail + PII

Students have no directory/sensitive split and no reporting-chain concept —
student-level data is inherently sensitive. A student row is shown at detail
within `student_detail_location_scope`; aggregates within
`student_summary_location_scope`; `student_pii_scope` (`all`/`none`) gates the
identifier columns on the detail view.

### "reporting chain"

A viewer's **reporting chain** is every staff member who reports up to them
through the org tree (direct + indirect), from `dim_staff_reporting_chain`. It
is strictly _downward_ — never same-level peers — and **unbounded by location or
department** — a report at another school is still in your reporting chain ("you
can never be hidden from your own manager").

### Per-field sensitive scope enum

Each sensitive staff field carries one scope value. It decides **both** whether
the column is visible **and** which rows it is visible for:

<!-- markdownlint-disable MD013 -->

| Scope value                     | Column shown? | Rows the field is visible for                                             |
| ------------------------------- | ------------- | ------------------------------------------------------------------------- |
| `none`                          | no            | —                                                                         |
| `all_in_scope`                  | yes           | all rows in `staff_detail_location_scope ∩ staff_detail_department_scope` |
| `reporting_chain_or_below_rank` | yes           | (in scope **∩** ranked below me) **∪** my reporting chain                 |
| `reporting_chain`               | yes           | my reporting chain only (unbounded by location/department)                |
| `teaching_staff`                | yes           | `job_function_code IN ('TEACH','TIR')` within scope                       |

<!-- markdownlint-enable MD013 -->

`job_function_level`: numerically greater = lower rank (1 = Chief, 6 = Teacher).
The **only union** is the reporting chain inside
`reporting_chain_or_below_rank`; everything else is an intersection. Applied
independently to `staff_pii_scope`, `staff_compensation_scope`,
`staff_observations_scope`, `staff_benefits_scope`, so a viewer can, e.g., see
contact info for everyone in their school (`all_in_scope`) but compensation only
for their reporting chain (`reporting_chain`).

**Multi-field queries intersect (most-restrictive wins).** A query pulling two
sensitive fields with different scopes returns the intersection of their row
sets — pull `pii = all_in_scope` + `comp = reporting_chain` together and you get
your reporting chain; pull `pii` alone and you get the whole school. This is the
standard "requesting a restricted field narrows the query" tradeoff.

### Location & department scopes

Shared axes (decomposed — no fused enums), evaluated separately for the summary
surface and the sensitive (detail) surface:

<!-- markdownlint-disable MD013 -->

| Axis                       | Values                                   | Bounds                                                                                                 |
| -------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `*_location_scope`         | `network` / `region` / `school` / `none` | `network` = no filter; `region` = `region_key` = mine; `school` = `abbreviation` = mine; `none` = deny |
| `staff_*_department_scope` | `all` / `own_group` / `none`             | `all` = no filter; `own_group` = `department_group` = mine; `none` = deny                              |

<!-- markdownlint-enable MD013 -->

`staff_detail_location_scope ∩ staff_detail_department_scope` bound the
`all_in_scope` / `reporting_chain_or_below_rank` / `teaching_staff` field values
(the `reporting_chain` value ignores them by design). `staff_summary_*` bound
the aggregate surface. `network` is only ever set intentionally by the mapping;
an unmatched region/school resolves to `none` (deny), never `network`. The
viewer's `region_key`, `location_abbreviation`, and `department_group` are
carried on `dim_staff_cube_access` so `cube.js` builds filters from the level.

### Summary (aggregate) surface

`staff_summary` exposes aggregate demographics and headcount/FTE breakdowns — no
row-level identifiers — bounded by
`staff_summary_location_scope ∩ staff_summary_department_scope`, deliberately
broader than the sensitive scope so a leader can benchmark against
region/network. Low-N suppression is tracked in
[#4237](https://github.com/TEAMSchools/teamster/issues/4237). (Open question:
with the directory open at row level, the summary surface's unique remaining job
is aggregate demographics — whether to keep it as a distinct view or fold it is
deferred.)

### Survey access — out of scope

Deferred to a separate plan; no survey column in v1.

## `dim_staff_cube_access` schema

One row per active+primary `staff_key`. Columns:

```text
staff_key                          -- PK
google_email                       -- JWT-boundary lookup only

region_key                         -- viewer identity (filter key)
location_abbreviation              -- viewer identity (filter key)
department_group                   -- viewer identity (filter key)
department_type                    -- instructional / non-instructional
entity                             -- KTAF / Region
job_function_code
job_function_level                 -- org rank 1-6

student_summary_location_scope     -- network / region / school / none
student_detail_location_scope      -- network / region / school / none
student_pii_scope                  -- all / none

staff_summary_location_scope       -- network / region / school / none
staff_summary_department_scope     -- all / own_group / none
staff_detail_location_scope        -- sensitive bound: network/region/school/none
staff_detail_department_scope      -- sensitive bound: all/own_group/none
staff_pii_scope                    -- sensitive scope enum (5 values; see table)
staff_compensation_scope           -- (same vocabulary)
staff_observations_scope           -- (same vocabulary)
staff_benefits_scope               -- (same vocabulary)
```

Removed vs the prior revision: `staff_detail_org_gate` (folded into the four
sensitive `*_scope` enums). The directory/employment columns are NOT in this
table — they live on `dim_staff` and are open; this table only carries the
access criteria.

## Source mappings (Google Sheets crosswalks)

The data team edits the sheet; `dim_staff_cube_access` joins the staged
crosswalks. Special-access `department` override wins entirely over the role
mapping when matched.

### `cube_access_role` columns

`job_function_code`, `entity` (`KTAF`/`Region`/`any`), `department_type`
(`instructional`/`non-instructional`/`any`), `job_function_level` (1-7), then
the access columns below. Keyed on the 3-part tuple.

### `cube_access_department_override` columns

`department` (exact `department_name`), then the same access columns. 8 rows:
Executive, Data, Human Resources, Leadership Development, Teacher Development,
Accounting, Finance, Compliance.

### Access columns (both tabs)

`student_summary_location_scope`, `student_detail_location_scope`,
`student_pii_scope`, `staff_summary_location_scope`,
`staff_summary_department_scope`, `staff_detail_location_scope`,
`staff_detail_department_scope`, `staff_pii_scope`, `staff_compensation_scope`,
`staff_observations_scope`, `staff_benefits_scope`. (No
`staff_detail_org_gate`.) The four `staff_*_scope` values use the per-field enum
(`none`/`all_in_scope`/`reporting_chain_or_below_rank`/`reporting_chain`/`teaching_staff`).

### `cube_access_department_rollup`

Unchanged: `department_name` → `department_group` + `department_type`.

## Changes required

### Source layer — built entirely from marts

`dim_staff_cube_access` and `dim_staff_reporting_chain` are assembled
**intra-mart** from the work-assignment dimensional star, filtered to each
person's **current primary** assignment (every join filters `is_current` and the
primary assignment). `job_function_code` on `dim_work_assignment_jobs` is the
prereq (landed, `f9dd839ed`). `staff_key` stays
`generate_surrogate_key([employee_number])`.

### `dim_staff_reporting_chain` — unchanged

Transitive closure of the current org tree, keyed on `staff_key`; self-pair at
`depth = 0`. `WITH RECURSIVE` → `contract: enforced: false`. Built and
validated.

### `dim_staff_cube_access` — reworked to the schema above

Primary-assignment spine → rollup → override-then-role join → coalesce
non-matches to the deny value (`none`). Carry the viewer identity keys. Drop
`staff_detail_org_gate`, `scope_level`, `scope_key`, `student_access_level`,
`staff_access_level`.

### `cube.js`: `contextToGroups`

Replace the Admin Directory API with BigQuery reads, cached to midnight ET. (1)
email → access row from `dim_staff_cube_access` (`WHERE google_email = @email`);
(2) `staff_key` → reporting-chain `staff_key`s from `dim_staff_reporting_chain`
(`WHERE manager_staff_key = @staffKey`). Cache
`{ row, reportingChainKeys, groups }`. `buildGroups(row)` emits column tiers:

- Students: `cube-access-student-detail` / `-summary` / `-pii` by the student
  scopes.
- Staff: `cube-access-staff-directory` for **every** staff viewer (the open
  directory); a sensitive column tier per the `*_scope` enums (`!= none`). In v1
  the only sensitive columns are PII → `cube-access-staff-pii` when
  `staff_pii_scope != none`.

### `cube.js`: `queryRewrite`

Reads the cached `row` + `reportingChainKeys`.

- **Directory-only staff query** → no row filter (all staff network-wide).
- **Staff query touching sensitive field(s)** → AND the per-field scope filters
  of every requested sensitive field (intersection). Each field's filter is
  built from its enum value:
  - `all_in_scope` → location ∩ department
  - `reporting_chain_or_below_rank` → (location ∩ department ∩ ranked below
    viewer) ∪ chain-IN
  - `reporting_chain` → chain-IN
  - `teaching_staff` → location ∩ department ∩ `job_function_code` in
    `('TEACH','TIR')`
  - `none` → the column is hidden by `access_policy`, never requested
- **Student query** → location filter by surface (`*_detail` vs `*_summary`),
  default-deny empty `IN ()`.
- Student-member strip, snapshot-anchor guard, and `canSwitchSqlUser` unchanged.

The staff views expose `staff.staff_key`, `staff.job_function_level`,
`staff.job_function_code`, `staff.department_group` (via the § "staff cube
join") for these filters.

### Cube schema test + `isStaffMember`

`tests/cube/test_cube_schema.py` (no `dim_`/`fct_` cube names) — DONE. Add an
`isStaffMember` prefix helper in `access.js`.

### No new Cubes for the access models

`dim_staff_cube_access` / `dim_staff_reporting_chain` get no cube/view. Sole
exception: the `staff` cube reads `job_function_level`, `job_function_code`,
`department_group` from `dim_staff_cube_access` via a `staff_key` `LEFT JOIN`
(never the access-policy columns).

### View access policies + `staff` cube join

- **Student views** (6): `cube-access-student-detail` (detail) / `-summary`
  (summary) / `-pii`.
- **Staff views**: `staff_detail` carries `cube-access-staff-directory`
  (`includes: "*"`, `excludes:` the sensitive fields — `personal_email`,
  `personal_cell_phone`, `birth_date`, `gender_identity`, `race`, `is_hispanic`)
  - `cube-access-staff-pii` (`includes: "*"`). `staff_summary` keeps a single
    aggregate tier.
- **`staff` cube**: inline `sql:` `LEFT JOIN dim_staff_cube_access` on
  `staff_key` exposing `job_function_level`, `job_function_code`,
  `department_group`; expose on `staff_detail` (and `department_group` on
  `staff_summary`).

### Google Workspace group cleanup

After live + validated, retire the `cube-*` Workspace groups (names are now
internal).

## Open questions

1. Department rollup (`department_name` → group / type) owned by the data team.
2. `job_function_code` — RESOLVED (prereq landed).
3. Multi-location / itinerant staff — one `location_abbreviation`; deferred.
4. Whether to keep `staff_summary` as a distinct view or fold it into the open
   directory (its only unique job is aggregate demographics) — deferred.

## Implementation sequence

1. Crosswalk sheet columns + `sources-external.yml` + staging contracts; data
   team re-fills; re-stage (`--target staging`).
2. Rework `dim_staff_cube_access`; keep `dim_staff_reporting_chain`. Validate
   1:1 on `staff_key`.
3. Confirm both dims in `exposures/cube.yml` `depends_on`.
4. `staff` cube inline join (`job_function_level` / `job_function_code` /
   `department_group`).
5. View `access_policy`: student `-detail`/`-summary`/`-pii`; staff
   `-directory`/`-pii`.
6. `cube.js` / `access.js`: BigQuery `contextToGroups`; `queryRewrite` with open
   directory + per-field sensitive scopes (intersection across requested
   sensitive fields); `isStaffMember`.
7. `tests/cube/test_cube_schema.py` — DONE.
8. Docs: `src/cube/CLAUDE.md` + staff view YAML (the #4092 gate).
9. Validate in Dev Mode per tier (directory open; sensitive fields scoped;
   reporting-chain-only vs in-scope vs below-rank; summary breadth > sensitive).
10. Deploy; spot-check.
11. Retire `cube-*` Workspace groups.
12. Data-quality follow-up (#4260) — aggregate counts only, no PII.
