# Cube Security Redesign — HR-Derived Access with Independent Summary / Detail Scopes

**Issue:** [#4102](https://github.com/TEAMSchools/teamster/issues/4102)
**Branch:** `cristinabaldor/feat/claude-cube-security-redesign`

**Revision history.** The original draft of this spec (2026-06-03) used a single
`scope_level` that capped both summary and detail visibility, plus boolean-ish
`*_access_level` tiers. This revision (2026-06-24) **supersedes** that model:
access is decomposed into **independent axes** — a separate summary scope and
detail scope per domain, with the location and department dimensions split apart
(no more fused `network_department_group` enums) and the staff reporting-chain /
rank gate as its own axis. Prior single-scope sections are preserved in git
history.

## Summary

Move all Cube access control into Cube itself, derived automatically from HR
data. Two dbt models are the source of truth, replacing manual Google Workspace
group enrollment and the Google Admin Directory API entirely:

- `dim_staff_cube_access` — one row per active+primary staff member (keyed on
  `staff_key`); resolves each person's **current role** to a set of orthogonal
  access axes (summary location scope, detail location scope, department scope,
  the staff org-relation gate, per-field visibility scopes, and the org rank).
  Derived from role (`job_function_code` × `entity` × `department_type`) with a
  department-level special-access override.
- `dim_staff_reporting_chain` — the transitive closure of the current org tree
  (manager → every direct/indirect report), keyed on `staff_key`, used to grant
  detail access to a manager's own downline.

Identity keys on `staff_key` (a stable surrogate of `employee_number`)
throughout. The JWT email claim is used in exactly one place — a boundary lookup
resolving email → `staff_key` — because Google emails are reused and unsafe as a
persistent identity key.

`cube.js` is simplified: `contextToGroups` queries BigQuery (no Directory API),
`queryRewrite` reads the cached access row and applies scope filters by view,
and all access criteria live in the dbt models + crosswalk sheets.

## Access model

### Three orthogonal axes

Access is no longer one fused scope. Each viewer resolves to independent axes
that compose by intersection (and, for the staff downline, union):

| Axis                       | Domain            | Purpose                                 |
| -------------------------- | ----------------- | --------------------------------------- |
| **Location scope**         | student + staff   | which region/school's rows              |
| **Department scope**       | staff only        | own department group vs all departments |
| **Org-relation gate**      | staff detail only | reporting chain / below rank            |
| **Field-visibility scope** | student + staff   | which sensitive columns                 |

The first three are evaluated **separately for the summary surface and the
detail surface**, so a viewer can have broad aggregate reach and narrow
row-level reach simultaneously.

### Summary vs detail are independent scopes

For each domain, two surfaces with **independently configured** breadth:

- **Summary** (aggregate, no row-level identifiers) — for headcount,
  demographic, and (when those cubes land) compensation / observation / survey
  trend reporting. Deliberately broader: a school leader can benchmark their
  school against the network.
- **Detail** (row-level, identifiers + PII) — tightly gated to the individuals a
  viewer is allowed to see.

The role crosswalk specifies **both** scopes per role (fully independent — e.g.
SL: summary = network, detail = school).

### Row composition

For a viewer querying a given surface:

- **Summary rows** = `summary_location_scope` **∩** `summary_department_scope`
  (staff) / `summary_location_scope` (student). No org-relation gate —
  aggregates do not chain-filter; sensitive aggregate **measures** are bounded
  by their field-visibility scope (below).
- **Detail rows (student)** = `detail_location_scope`.
- **Detail rows (staff)** = ( `detail_location_scope` ∩
  `detail_department_scope` ∩ below-rank filter ) **∪** **downline**
  (`staff_key ∈` viewer's reporting chain, regardless of location/department).

The **union with downline** honors the "you can never be hidden from your own
manager" guarantee: a report at another school, outside the viewer's location
scope, is still visible at detail. (The prior single-scope spec treated detail
as a strict subset of the location scope and silently dropped such
cross-location reports — fixed here.)

### Location scope

<!-- markdownlint-disable MD013 -->

| `*_location_scope` | Visible rows                                  |
| ------------------ | --------------------------------------------- |
| `network`          | all (no location filter)                      |
| `region`           | rows whose `region_key` equals the viewer's   |
| `school`           | rows whose `abbreviation` equals the viewer's |
| `none`             | nothing (default deny for that surface)       |

<!-- markdownlint-enable MD013 -->

`network` is the broadest grant and is **only ever set intentionally** by the
role/department mapping. A person who fails to match any region/school does
**not** fall through to `network` — they resolve to `none`. The viewer's
identity (`region_key`, `location_abbreviation`) is carried on
`dim_staff_cube_access` so `cube.js` can build the filter from the level.

### Department scope (staff only)

<!-- markdownlint-disable MD013 -->

| `staff_*_department_scope` | Visible rows                                      |
| -------------------------- | ------------------------------------------------- |
| `all`                      | no department filter                              |
| `own_group`                | rows whose `department_group` equals the viewer's |
| `none`                     | nothing                                           |

<!-- markdownlint-enable MD013 -->

Composes with location by intersection (e.g. a regional director:
`location_scope = region` ∩ `department_scope = own_group`). The viewer's
`department_group` is carried on `dim_staff_cube_access`.

### Staff org-relation gate (detail only)

Narrows the staff **detail** rows within the location ∩ department scope, then
unions the downline.

<!-- markdownlint-disable MD013 -->

| `staff_detail_org_gate`  | Detail rows (within location ∩ department scope)   | Roles                                |
| ------------------------ | -------------------------------------------------- | ------------------------------------ |
| `all_in_scope`           | every row in scope (no rank/chain narrowing)       | special-access departments           |
| `below_rank_or_downline` | `job_function_level >` viewer's **OR** in downline | leadership (CHIEF/EDHOS/SL/DSO/ASL)  |
| `downline_only`          | in downline only                                   | managers and individual contributors |
| `none`                   | nothing                                            | default deny                         |

<!-- markdownlint-enable MD013 -->

`job_function_level`: numerically greater = lower rank (1 = Chief, 6 = Teacher).
The downline (`dim_staff_reporting_chain`) is **unioned** regardless of
location, per Row composition above. Same-level peers who do not report to the
viewer satisfy neither branch and are never shown at detail — that keeps Chiefs
from seeing other Chiefs.

### Field-visibility scope (columns)

`student_pii_scope`, `staff_pii_scope`, `staff_compensation_scope`,
`staff_observations_scope`, `staff_benefits_scope` are **enums** over a shared
vocabulary, gating columns on top of the row scopes:

<!-- markdownlint-disable MD013 -->

| Scope value       | Field visible for…                                           |
| ----------------- | ------------------------------------------------------------ |
| `all`             | every row the viewer sees on that surface                    |
| `reporting_chain` | only the viewer's downline rows (staff)                      |
| `teaching_staff`  | only staff with `job_function_code IN ('TEACH','TIR')` (ASL) |
| `none`            | never                                                        |

<!-- markdownlint-enable MD013 -->

`reporting_chain` / `teaching_staff` are **row-conditional column visibility** —
the column is included by the view's `access_policy`, and `queryRewrite` narrows
the query's **rows** to the downline (or `TEACH`/`TIR`) when such a column is
requested (see [§ View pattern](#view-pattern)). `student_pii_scope` is `all` /
`none` in v1 (future `own_roster` deferred). `staff_compensation_scope` /
`staff_observations_scope` gate columns/cubes that **do not exist yet** —
forward-compat (see
[§ Forward-compat](#forward-compat-comp--observations--survey)).

### Survey access — out of scope

Survey results access is deferred to a separate plan. `dim_staff_cube_access`
carries no survey column in v1; the survey plan adds it when survey cubes are
built.

## Resolution order (`dim_staff_cube_access`)

One row per active+primary staff member, keyed on `staff_key`
(`generate_surrogate_key([employee_number])`). `google_email` is carried as a
populated lookup column so `contextToGroups` can resolve the JWT claim. Each row
resolves as:

```text
1. Assemble the current primary assignment from the marts star
   (dim_staff_work_assignments + dim_work_assignment_{jobs,
    organizational_units, locations, primary} + dim_staff), all is_current,
    is_primary_position. staff_key + region_key + abbreviation + department_*
    come from the star; google_email from dim_staff; job_function_code from
    dim_work_assignment_jobs.

2. Join the department rollup crosswalk (department_name → department_group,
   department_type).

3. If department_name ∈ special-access list (override crosswalk):
     → emit the override row verbatim (network-broad scopes, *_scope columns).
       The override wins entirely (no field-by-field merge).

4. Else: join the role crosswalk on (job_function_code, entity, department_type)
   and emit its summary/detail location + department scopes, org gate,
   *_scope columns, and job_function_level.

5. Any crosswalk non-match coalesces every access column to 'none' (deny). A
   location-bound scope whose key can't resolve downgrades that scope to 'none'.

6. JWT email matches no row (terminated, recycled, contractor, service account)
   or a null email → no resolution → contextToGroups returns [] → default deny.
```

### Department match

Special-access `department` matches the current assignment's `department_name`
(`dim_work_assignment_organizational_units`, `assignment_type = 'home'`) by
exact string equality. `Accounting and Compliance` is not matched by
`Accounting` or `Compliance` under exact equality — it falls to the role-based
path (data-quality follow-up, #4260).

## Source mappings

The canonical reference for job groupings and org levels is the
[job groupings explorer](https://teamschools.github.io/job_groupings/website/explorer.html).
The criteria are **materialized as Google Sheets crosswalks** (repo lookup-table
convention). The data team edits the sheet; `dim_staff_cube_access` joins the
staged crosswalks — these tables are the authoritative content, not in-SQL
`CASE` blocks.

### Role-based mapping — `cube_access_role`

Keyed on the 3-part tuple (`job_function_code`, `entity`, `department_type`).
`job_function_level` is the org rank (1 = highest). Columns:

<!-- markdownlint-disable MD013 -->

| Column                                                                                               | Values                                                       |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `job_function_code` / `entity` / `department_type`                                                   | join key (`entity`/`department_type` accept `any`)           |
| `job_function_level`                                                                                 | 1–6                                                          |
| `student_summary_location_scope`                                                                     | network / region / school / none                             |
| `student_detail_location_scope`                                                                      | network / region / school / none                             |
| `student_pii_scope`                                                                                  | all / none                                                   |
| `staff_summary_location_scope`                                                                       | network / region / school / none                             |
| `staff_summary_department_scope`                                                                     | all / own_group / none                                       |
| `staff_detail_location_scope`                                                                        | network / region / school / none                             |
| `staff_detail_department_scope`                                                                      | all / own_group / none                                       |
| `staff_detail_org_gate`                                                                              | all_in_scope / below_rank_or_downline / downline_only / none |
| `staff_pii_scope` / `staff_compensation_scope` / `staff_observations_scope` / `staff_benefits_scope` | all / reporting_chain / teaching_staff / none                |

<!-- markdownlint-enable MD013 -->

The data team fills the summary and detail scopes **independently** per role.
Indicative intent (subject to data-team confirmation): leadership roles
(CHIEF/EDHOS/SL/DSO/ASL) carry `staff_detail_org_gate = below_rank_or_downline`;
managers and individual contributors carry `downline_only`; special-access
departments carry `all_in_scope`. Summary scopes are typically broader than
detail (e.g. school-detail with region- or network-summary for benchmarking).

### Department special-access override — `cube_access_department_override`

Same access columns as the role table (minus the role-tuple keys), keyed on
`department`. Applies regardless of `job_function_code`; broad scopes,
`staff_detail_org_gate = all_in_scope`, `*_scope` columns unconditional `all` /
`none`. The override wins entirely when matched. Special-access departments:
Executive, Data, Human Resources, Leadership Development, Teacher Development,
Accounting, Finance, Compliance.

### Department rollup — `cube_access_department_rollup`

Unchanged: `department_name` → `department_group` + `department_type`. Owned by
the data team (open question 1).

## Changes required

### Source layer — built entirely from marts

Both new models are assembled **intra-mart** from the work-assignment
dimensional star, filtered to each staff member's **current primary**
assignment. They do **not** `ref()` `int_people__staff_roster` —
`marts/CLAUDE.md` forbids ref-into-marts and permits intra-mart refs.

The star (all keyed on `work_assignment_key`, joined to the current primary
assignment):

<!-- markdownlint-disable MD013 -->

| Source mart                                   | Supplies                                                        |
| --------------------------------------------- | --------------------------------------------------------------- |
| `dim_staff_work_assignments`                  | `staff_key` ↔ `work_assignment_key`, `is_current`               |
| `dim_staff`                                   | `google_email`, person attributes                               |
| `dim_work_assignment_jobs`                    | `job_function_code`, position                                   |
| `dim_work_assignment_organizational_units`    | `department_name`, `business_unit_name` (`type='home'`)         |
| `dim_work_assignment_locations`               | `location_key` → `dim_locations` (`region_key`, `abbreviation`) |
| `dim_work_assignment_primary`                 | `is_primary_position`                                           |
| `dim_work_assignment_reporting_relationships` | `manager_staff_key` (per assignment)                            |

<!-- markdownlint-enable MD013 -->

**Current role only:** every join filters `is_current` and the primary
assignment. `staff_key` stays `generate_surrogate_key([employee_number])`,
identical to `dim_staff`.

#### Prerequisite: `job_function_code` on `dim_work_assignment_jobs` — DONE

Added on this branch (`f9dd839ed`) as a passthrough select (not a
`generate_surrogate_key` input → no hash churn). All access keys use the code,
not the free-text label.

### 1. dbt model: `dim_staff_reporting_chain` — unchanged

Transitive closure of the current org tree, keyed on `staff_key`. Grain:
`(manager_staff_key, reportee_staff_key)`; self-pair at `depth = 0`.
`WITH RECURSIVE` → `contract: enforced: false`. Built and validated (8,041
pairs, max depth 7). No change in this revision.

### 2. dbt model: `dim_staff_cube_access` — reworked

One row per active+primary `staff_key`. Columns:

```text
staff_key                          -- PK
google_email                       -- JWT-boundary lookup only

region_key                         -- viewer identity
location_abbreviation              -- viewer identity
department_group                   -- viewer identity (rollup)
department_type                    -- instructional / non-instructional
entity                             -- KTAF / Region
job_function_code
job_function_level                 -- org rank 1–6

student_summary_location_scope     -- network / region / school / none
student_detail_location_scope      -- network / region / school / none
student_pii_scope                  -- all / none

staff_summary_location_scope       -- network / region / school / none
staff_summary_department_scope     -- all / own_group / none
staff_detail_location_scope        -- network / region / school / none
staff_detail_department_scope      -- all / own_group / none
staff_detail_org_gate              -- org gate: see § Staff org-relation gate
staff_pii_scope                    -- all / reporting_chain / teaching_staff / none
staff_compensation_scope           -- all / reporting_chain / teaching_staff / none
staff_observations_scope           -- all / reporting_chain / teaching_staff / none
staff_benefits_scope               -- all / reporting_chain / teaching_staff / none
```

Removed vs the prior model: `scope_level`, `scope_key`, `student_access_level`,
`staff_access_level` (their meaning is now split across the axes above). The SQL
keeps its shape (primary-assignment spine → rollup → override-then-role join →
coalesce non-matches to `none`); only projected columns change. Carry the viewer
identity keys (`region_key`, `location_abbreviation`, `department_group`)
explicitly so `cube.js` builds filters from the level. `*_access_level`-style
no-access emits the string `'none'` (never NULL).

### 3. `cube.js`: `contextToGroups`

Replace the Admin Directory API with BigQuery reads, cached to midnight ET.
**Email is used only here**, to resolve the JWT claim to a stable `staff_key`.

1. Resolve `email` → access row from `kipptaf_marts.dim_staff_cube_access`
   (`WHERE google_email = @email LIMIT 1`).
2. Resolve `row.staff_key` → `reportee_staff_key[]` from
   `kipptaf_marts.dim_staff_reporting_chain`
   (`WHERE manager_staff_key = @staffKey`).
3. Cache `{ row, reporteeStaffKeys, groups, expiresAt }`. `buildGroups(row)`
   emits the view-policy group names. `CUBE_GROUP_MAP` local-dev bypass stays;
   no Google groups read.

**Group emission** (column-visibility tiers the views gate on):

- Students: `cube-access-student-detail` (if
  `student_detail_location_scope != none`), `cube-access-student-summary` (if
  `student_summary_location_scope != none`), `cube-access-student-pii` (if
  `student_pii_scope = all`). Detail viewers also get `-summary`.
- Staff: `cube-access-staff-detail` / `-summary` (if the respective scope
  `!= none`), `cube-access-staff-pii` (if `staff_pii_scope != none`). Detail
  viewers also get `-summary`.

### 4. `cube.js`: `queryRewrite`

Reads the cached `row` + `reporteeStaffKeys`; branches on the **view prefix** in
the query members (`*_summary.*` vs `*_detail.*`).

- **Summary view** → `summary_location_scope` ∩ `summary_department_scope`
  (staff) / `summary_location_scope` (student). No org gate.
- **Detail view (student)** → `detail_location_scope`.
- **Detail view (staff)** → ( `detail_location_scope` ∩
  `detail_department_scope` ∩ below-rank ) **∪**
  `staff.staff_key IN reporteeStaffKeys`. The `staff_detail_org_gate` selects
  which branches fire.
- **Student-member strip**: members where `isStudentMember` is true are removed
  when the viewer lacks any student access.
- **Row-conditional columns**: when a `reporting_chain` /
  `teaching_staff`-scoped sensitive column is requested, narrow rows to the
  downline / `job_function_code IN ('TEACH','TIR')`.
- **Default deny**: no scope → empty `IN ()` filter.
- **Snapshot anchor guard** and `canSwitchSqlUser` unchanged.

Location filters route through each view's `locations` join (`region_key` /
`abbreviation`). The staff views expose `staff.staff_key`,
`staff.job_function_level`, `staff.job_function_code`, and
`staff.department_group` (via the § 6 join) for the detail and department
filters.

### 5. Cube schema test + `isStaffMember`

- Add `tests/cube/test_cube_schema.py` enforcing no `dim_` / `fct_` prefix on
  cube names.
- Add an `isStaffMember` prefix helper (parallels `isStudentMember`); drop any
  static cube arrays (already absent — current `cube.js` is prefix-based).

### 5a. No new Cubes for the access models

`dim_staff_cube_access` and `dim_staff_reporting_chain` are read by `cube.js` as
raw BigQuery tables — they **are** the access policy and get **no** cube/view
definition (exposing them as queryable Cubes would subject them to the policies
they encode). The only Cube-side dbt wiring is adding both to
`cube_semantic_layer.depends_on` in `exposures/cube.yml`.

Exception, narrowly scoped: the `staff` cube reads `job_function_level`,
`job_function_code`, and `department_group` from `dim_staff_cube_access` via a
`LEFT JOIN` on `staff_key` (see § 6). Only those three org-fact columns are
exposed — never the access-policy columns — so the no-leak intent holds. They
are the viewee-side members the row filters compare against:
`job_function_level` (below-rank gate), `job_function_code` (`teaching_staff`
narrowing), and `department_group` (department scope).

### 6. View access policies + `staff` cube join

- **Student views** (6): rename `cube-access-student-data` → `-detail` (the 3
  detail views) / `-summary` (the 3 summary views); keep `-pii` on detail.
- **Staff views** (2): rename `cube-access-staff-data` → `-detail`
  (`staff_detail`) / `-summary` (`staff_summary`); keep `-pii` on
  `staff_detail`.
- **`staff` cube**: convert from bare `sql_table: kipptaf_marts.dim_staff` to
  inline `sql:` that `LEFT JOIN`s `dim_staff_cube_access` on `staff_key`,
  exposing only `job_function_level`, `job_function_code`, and
  `department_group` (1:1, no fan-out). Expose all three on `staff_detail`, and
  `department_group` on `staff_summary` too (the department scope applies to
  both surfaces), for the row filters. (Why the Cube layer, not `dim_staff.sql`:
  `dim_staff_cube_access` already `ref()`s `dim_staff`, so the reverse ref would
  be circular, and marts can't pull it from a shared intermediate per
  `marts/CLAUDE.md`.)

### 7. Google Workspace group cleanup

After the redesign is live and validated (at least one full school day in
production, spot-checked per tier), retire all `cube-*` Google Workspace groups.
The group names are now manufactured internally by `contextToGroups` from the
dbt row — they are no longer Workspace groups, so renaming the view tiers to
`-detail`/`-summary`/`-pii` is atomic within this PR (not a coordinated external
deploy). Retirement is cleanup of now-unused Workspace groups.

## View pattern

The student domain already implements the detail/summary split: a detail view
exposes row-level identifiers (gated by a base tier + a `-pii` tier), a summary
view omits identifiers and carries demographics as aggregate breakdowns only.
The staff domain follows the same shape. This redesign:

- Renames the base tiers to distinguish **detail-surface access** from
  **summary-surface access** (`-detail` vs `-summary`), so a summary-only viewer
  cannot reach a detail view. Detail viewers also hold `-summary` (so they see
  both surfaces).
- Keeps row gating (location/department/org-relation) in `queryRewrite` —
  `access_policy` cannot express the dynamic `IN (reportee list)` or the
  rank/chain OR. `queryRewrite` tells summary from detail by the view prefix.

### The `member_level` intersection constraint

`member_level` `access_policy` blocks **intersect, not union** (#4102 Finding,
PR #3755): a viewer in two blocks gets the intersection of their `includes`
lists. So **column visibility resolves to exactly one composite block per
viewer** for any view whose columns span multiple field-visibility scopes.
`contextToGroups` resolves the viewer's full column set into a single group;
each view carries one block per composite tier. In v1 the only staff column axis
is PII (comp/obs columns do not exist yet), so the `-detail` (excludes PII) +
`-pii` (includes `*`) two-tier split suffices and each viewer is in exactly one.
When comp/obs cubes land, the composite block absorbs those columns; row
narrowing for `reporting_chain` / `teaching_staff` stays in `queryRewrite`.

## Forward-compat (comp / observations / survey)

`staff_compensation_scope` and `staff_observations_scope` are carried on
`dim_staff_cube_access` and wired into `queryRewrite`'s row-conditional logic
now, but they gate columns/cubes that **do not exist yet**. When the
compensation and observation cubes are built, their sensitive columns slot into
the staff views' composite column tier and inherit the row-conditional narrowing
with no model change. Survey access is fully deferred (no column in v1).

## Open questions

1. **`department_group` / `department_type` rollup** — the mapping from
   `department_name` values into department groups and the
   instructional/non-instructional split is owned by the data team and lives in
   the department rollup crosswalk.
2. **`job_function_code` availability** — RESOLVED (prereq landed; code values
   verified in prod).
3. **Row-conditional restriction** — requesting a `reporting_chain` /
   `teaching_staff` sensitive field restricts the staff result set to the
   viewer's downline / teaching staff for that query. Confirm acceptable with
   the data team before implementing staff column gating.
4. **Multi-location / itinerant staff** — coaches covering multiple schools get
   one `location_abbreviation`; multi-location support is deferred.

## Implementation sequence

1. **Crosswalks:** update `cube_access_role` + `cube_access_department_override`
   sheet columns to the new scope axes; declare the new columns in
   `sources-external.yml`; data team re-fills the rows; re-stage with
   `stage_external_sources --target staging`.
2. **`dim_staff_cube_access`:** rework projected columns to the new schema; keep
   `dim_staff_reporting_chain` as-is. Validate 1:1 on `staff_key`, tests pass.
3. **`exposures/cube.yml`:** confirm both dims in
   `cube_semantic_layer.depends_on`.
4. **`staff` cube:** inline `sql:` join for `job_function_level` /
   `job_function_code`; expose on `staff_detail`.
5. **View `access_policy`:** rename student + staff tiers to
   `-detail`/`-summary`/`-pii`.
6. **`cube.js`:** rewrite `contextToGroups` (two BigQuery reads) and
   `queryRewrite` (summary vs detail by view prefix; location ∩ department ∩
   org-gate ∪ downline; row-conditional columns); add `isStaffMember`.
7. **`tests/cube/test_cube_schema.py`.**
8. **Docs:** `src/cube/CLAUDE.md` + staff view YAML documenting the gate
   (#4092).
9. **Validate in Dev Mode** with test emails at each tier (network/region/school
   summary vs detail, manager-with-reportees, special-access department, no
   access; confirm a pii viewer sees PII; confirm summary breadth > detail).
10. **Deploy to production; spot-check each tier.**
11. **Retire all `cube-*` Google Workspace groups.**
12. **Data-quality issue** (#4260) for staff whose current assignment can't
    resolve a role (aggregate counts only — no PII).
