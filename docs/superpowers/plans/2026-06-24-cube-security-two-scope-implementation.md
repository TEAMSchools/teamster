# Cube Security Two-Scope Access Model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all Cube access control into Cube itself, derived from HR data,
using independent summary/detail scopes per domain (location × department ×
org-relation axes) and removing the Google Admin Directory API.

**Architecture:** `dim_staff_cube_access` (one row per active+primary
`staff_key`) resolves each person's current role to orthogonal access axes via
the Google Sheets crosswalks. `cube.js` reads that row (by `google_email`) plus
`dim_staff_reporting_chain` (by `manager_staff_key`) at login, caches to
midnight ET, and `queryRewrite` applies per-surface row filters. Pure resolution
logic lives in `src/cube/access.js` (unit-tested with `node --test`); `cube.js`
owns I/O and caching.

**Tech Stack:** dbt (BigQuery), Cube semantic layer (`cube.js` + YAML), Node.js
(`@google-cloud/bigquery`, `node --test`), pytest.

**Authoritative spec:**
[`docs/superpowers/specs/2026-06-03-cube-security-redesign.md`](../specs/2026-06-03-cube-security-redesign.md)
(read it first).

> **⚠️ Refold pending (spec revision 2026-06-24b).** This plan was written
> against the earlier per-axis model that included `staff_detail_org_gate`. The
> spec has since refolded to: **staff directory open** (only sensitive fields
> gated), the org-gate **folded into a self-contained per-field scope enum**
> (`none` / `all_in_scope` / `team_or_below_rank` / `team` / `teaching_staff`),
> and the term **`team`** replacing "reporting chain" / "downline". Tasks **1,
> 2, 4, 6, 7** must be regenerated against the current spec before execution —
> and the already-committed Task 6 `access.js` (`3b06b542f`) encodes the OLD
> model, so it will be reworked on resume. Tasks **5** (student view renames)
> and **8** (schema test, done) are unaffected. The crosswalk CSVs in the
> session scratchpad are current.

## Global Constraints

- **dbt CLI**: always `uv run dbt ...`; never bare `dbt`/`python`.
- **Marts contract**: `marts/` inherit `contract: enforced: true` +
  `materialized: view`; every mart needs an explicit uniqueness test on its PK.
  Do not restate contract/materialized per model.
- **Staging contract**: kipptaf `staging/` inherit `contract: enforced: true` +
  `materialized: table`; staging tests MUST set `config: severity: error`.
- **Generic-test syntax (dbt 1.11+)**: `accepted_values` / `relationships` /
  `dbt_utils.*` nest args under `arguments:`.
- **No `select *` in a mart final SELECT** — enumerate columns.
- **Cube conventions**: cubes `public: false`; one cube/view per file; `name:`
  matches filename and carries no `dim_`/`fct_` prefix. Never use the Playground
  Models tab. No manual deploy step (merge to `main` redeploys).
- **Access group names are internal** — manufactured by `contextToGroups` from
  the dbt row, not Google Workspace groups. Renaming view tiers is atomic in
  this PR.
- **`dim_staff_cube_access` / `dim_staff_reporting_chain` get NO cube/view
  definition** (they are the access policy). Only exception: the `staff` cube
  reads `job_function_level` / `job_function_code` / `department_group` from
  `dim_staff_cube_access` via a `staff_key` join — never the access-policy
  columns.
- **PII stays local** — never emit PII values to PR/commit/issue/Slack. Redact
  in any external write.
- **Trunk**: don't run `trunk fmt`/`check` for normal commits
  (pre-commit/pre-push hooks handle it), but run
  `/workspaces/teamster/.trunk/tools/trunk check --force <files>` on any `.md` /
  `.sql` / `.yml` you change before declaring it lint-clean (markdownlint /
  sqlfluff / yamllint fire only at pre-push). Run from the repo root (not a
  worktree path).
- **dbt local validation**: build marts with
  `uv run dbt build --select <model> --target dev --defer --favor-state --state src/dbt/kipptaf/target/prod --project-dir src/dbt/kipptaf`.
  `--target prod` builds are classifier-blocked — hand prod runs to the user.

## Prerequisites (human / out-of-band)

These gate the dbt validation steps and are NOT agent-codeable:

1. **`job_function_code` on `dim_work_assignment_jobs`** — DONE (`f9dd839ed`).
2. **Crosswalk sheet update** — the data team must add the new scope columns
   (Task 1) to the `cube_access_role` and `cube_access_department_override` tabs
   of the access Google Sheet (`1TuH7e2AuxP-_dUImtHrWCXJ_S_KD_eYCRqWhbGcD2V4`)
   and fill the summary/detail scopes per role, then the externals must be
   re-staged:
   `uv run dbt run-operation stage_external_sources --args 'select: google_sheets.src_google_sheets__people__cube_access_role google_sheets.src_google_sheets__people__cube_access_department_override' --target staging --project-dir src/dbt/kipptaf`
   (`stage_external_sources --target staging` needs direct user authorization).
   Until this lands, Task 1–2 SQL/YAML can be written but the `dbt build` / test
   steps will fail on the missing columns.

---

### Task 1: Crosswalk source schema + staging contracts

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml:1830-1854`
  (`cube_access_role` columns), `:1872-1890` (`cube_access_department_override`
  columns)
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__cube_access_role.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__cube_access_department_override.yml`

**Interfaces:**

- Produces: staging models `stg_google_sheets__people__cube_access_role` and
  `…_department_override` carrying columns: (role only) `job_function_code`,
  `entity`, `department_type`, `job_function_level`; (both)
  `student_summary_location_scope`, `student_detail_location_scope`,
  `student_pii_scope`, `staff_summary_location_scope`,
  `staff_summary_department_scope`, `staff_detail_location_scope`,
  `staff_detail_department_scope`, `staff_detail_org_gate`, `staff_pii_scope`,
  `staff_compensation_scope`, `staff_observations_scope`,
  `staff_benefits_scope`. Override is keyed on `department` instead of the role
  tuple.

- [ ] **Step 1: Replace the `cube_access_role` source columns**

In `sources-external.yml`, replace the `columns:` block of
`src_google_sheets__people__cube_access_role` (drop `scope_level`,
`student_access_level`, `staff_access_level`) with:

```yaml
columns:
  - name: job_function_code
    data_type: string
  - name: entity
    data_type: string
  - name: department_type
    data_type: string
  - name: job_function_level
    data_type: int64
  - name: student_summary_location_scope
    data_type: string
  - name: student_detail_location_scope
    data_type: string
  - name: student_pii_scope
    data_type: string
  - name: staff_summary_location_scope
    data_type: string
  - name: staff_summary_department_scope
    data_type: string
  - name: staff_detail_location_scope
    data_type: string
  - name: staff_detail_department_scope
    data_type: string
  - name: staff_detail_org_gate
    data_type: string
  - name: staff_pii_scope
    data_type: string
  - name: staff_compensation_scope
    data_type: string
  - name: staff_observations_scope
    data_type: string
  - name: staff_benefits_scope
    data_type: string
```

- [ ] **Step 2: Replace the `cube_access_department_override` source columns**

Same column set as Step 1 but keyed on `department` (no role tuple):

```yaml
columns:
  - name: department
    data_type: string
  - name: student_summary_location_scope
    data_type: string
  - name: student_detail_location_scope
    data_type: string
  - name: student_pii_scope
    data_type: string
  - name: staff_summary_location_scope
    data_type: string
  - name: staff_summary_department_scope
    data_type: string
  - name: staff_detail_location_scope
    data_type: string
  - name: staff_detail_department_scope
    data_type: string
  - name: staff_detail_org_gate
    data_type: string
  - name: staff_pii_scope
    data_type: string
  - name: staff_compensation_scope
    data_type: string
  - name: staff_observations_scope
    data_type: string
  - name: staff_benefits_scope
    data_type: string
```

- [ ] **Step 3: Update the role staging properties (contract + tests)**

Replace the `columns:` list in
`staging/properties/stg_google_sheets__people__cube_access_role.yml` so the
contract matches the new source. Keep the
`dbt_utils.unique_combination_of_columns` on (`job_function_code`, `entity`,
`department_type`) and `not_null` on those three. Add `accepted_values` (nested
under `arguments:`, `config: severity: error`) for the enum columns:

```yaml
- name: student_summary_location_scope
  data_type: string
  description: Student summary aggregate breadth.
  data_tests:
    - accepted_values:
        arguments:
          values: [network, region, school, none]
        config:
          severity: error
- name: student_detail_location_scope
  data_type: string
  description: Student detail (row-level) breadth.
  data_tests:
    - accepted_values:
        arguments:
          values: [network, region, school, none]
        config:
          severity: error
- name: staff_summary_location_scope
  data_type: string
  description: Staff summary aggregate location breadth.
  data_tests:
    - accepted_values:
        arguments:
          values: [network, region, school, none]
        config:
          severity: error
- name: staff_detail_location_scope
  data_type: string
  description: Staff detail location breadth.
  data_tests:
    - accepted_values:
        arguments:
          values: [network, region, school, none]
        config:
          severity: error
- name: staff_summary_department_scope
  data_type: string
  description: Staff summary department breadth.
  data_tests:
    - accepted_values:
        arguments:
          values: [all, own_group, none]
        config:
          severity: error
- name: staff_detail_department_scope
  data_type: string
  description: Staff detail department breadth.
  data_tests:
    - accepted_values:
        arguments:
          values: [all, own_group, none]
        config:
          severity: error
- name: staff_detail_org_gate
  data_type: string
  description: Staff detail reporting-chain / rank gate.
  data_tests:
    - accepted_values:
        arguments:
          values: [all_in_scope, below_rank_or_downline, downline_only, none]
        config:
          severity: error
- name: student_pii_scope
  data_type: string
  description: Student PII field visibility.
  data_tests:
    - accepted_values:
        arguments:
          values: [all, none]
        config:
          severity: error
- name: staff_pii_scope
  data_type: string
  description: Staff PII field visibility.
  data_tests:
    - accepted_values:
        arguments:
          values: [all, reporting_chain, teaching_staff, none]
        config:
          severity: error
- name: staff_compensation_scope
  data_type: string
  description: Staff compensation field visibility (same vocabulary).
  data_tests:
    - accepted_values:
        arguments:
          values: [all, reporting_chain, teaching_staff, none]
        config:
          severity: error
- name: staff_observations_scope
  data_type: string
  description: Staff observation field visibility (same vocabulary).
  data_tests:
    - accepted_values:
        arguments:
          values: [all, reporting_chain, teaching_staff, none]
        config:
          severity: error
- name: staff_benefits_scope
  data_type: string
  description: Staff benefits field visibility (same vocabulary).
  data_tests:
    - accepted_values:
        arguments:
          values: [all, reporting_chain, teaching_staff, none]
        config:
          severity: error
```

Keep `job_function_code` / `entity` / `department_type` / `job_function_level`
entries (descriptions unchanged).

- [ ] **Step 4: Update the override staging properties**

Mirror Step 3 in
`staging/properties/stg_google_sheets__people__cube_access_department_override.yml`:
replace the column list with `department` (keyed, `not_null` + the table's
uniqueness test on `department`) plus the same scope/enum columns and
`accepted_values` tests. Drop `scope_level` / `student_access_level` /
`staff_access_level`.

- [ ] **Step 5: Parse-validate the schema**

Run: `uv run dbt parse --target staging --project-dir src/dbt/kipptaf` Expected:
parses with no errors (validates YAML + contract column refs; does not hit the
warehouse).

- [ ] **Step 6: Lint + commit**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force src/dbt/kipptaf/models/google/sheets/sources-external.yml src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__cube_access_role.yml src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__cube_access_department_override.yml`
Expected: No issues.

```bash
git add src/dbt/kipptaf/models/google/sheets/sources-external.yml \
  src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__cube_access_role.yml \
  src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__people__cube_access_department_override.yml
git commit -m "feat(dbt): two-scope columns on cube access crosswalks"
```

---

### Task 2: Rework `dim_staff_cube_access`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml`
- Verify (no edit expected): `src/dbt/kipptaf/models/exposures/cube.yml` already
  lists `ref("dim_staff_cube_access")` + `ref("dim_staff_reporting_chain")` in
  `cube_semantic_layer.depends_on`.

**Interfaces:**

- Consumes: Task 1 staging crosswalks.
- Produces: `kipptaf_marts.dim_staff_cube_access` with columns `staff_key`,
  `google_email`, `region_key`, `location_abbreviation`, `department_group`,
  `department_type`, `entity`, `job_function_code`, `job_function_level`,
  `student_summary_location_scope`, `student_detail_location_scope`,
  `student_pii_scope`, `staff_summary_location_scope`,
  `staff_summary_department_scope`, `staff_detail_location_scope`,
  `staff_detail_department_scope`, `staff_detail_org_gate`, `staff_pii_scope`,
  `staff_compensation_scope`, `staff_observations_scope`,
  `staff_benefits_scope`. 1:1 on `staff_key`. Read by `cube.js` (Task 7).

- [ ] **Step 1: Rework the model SQL**

Replace the `matched`, `scoped`, and final `select` of
`dim_staff_cube_access.sql`. The `primary_assignment` → `primary_deduped` →
`current_assignment` → `enriched` CTEs are unchanged except `current_assignment`
must also project `loc.region_key`, `loc.abbreviation as location_abbreviation`,
which it already does. New `matched` + final select:

```sql
    matched as (
        select
            e.staff_key,
            e.google_email,
            e.job_function_code,
            e.entity,
            e.department_type,
            e.department_group,
            e.region_key,
            e.location_abbreviation,

            rl.job_function_level,

            coalesce(
                ovr.student_summary_location_scope,
                rl.student_summary_location_scope,
                'none'
            ) as student_summary_location_scope,
            coalesce(
                ovr.student_detail_location_scope,
                rl.student_detail_location_scope,
                'none'
            ) as student_detail_location_scope,
            coalesce(
                ovr.student_pii_scope, rl.student_pii_scope, 'none'
            ) as student_pii_scope,

            coalesce(
                ovr.staff_summary_location_scope,
                rl.staff_summary_location_scope,
                'none'
            ) as staff_summary_location_scope,
            coalesce(
                ovr.staff_summary_department_scope,
                rl.staff_summary_department_scope,
                'none'
            ) as staff_summary_department_scope,
            coalesce(
                ovr.staff_detail_location_scope,
                rl.staff_detail_location_scope,
                'none'
            ) as staff_detail_location_scope,
            coalesce(
                ovr.staff_detail_department_scope,
                rl.staff_detail_department_scope,
                'none'
            ) as staff_detail_department_scope,
            coalesce(
                ovr.staff_detail_org_gate, rl.staff_detail_org_gate, 'none'
            ) as staff_detail_org_gate,
            coalesce(
                ovr.staff_pii_scope, rl.staff_pii_scope, 'none'
            ) as staff_pii_scope,
            coalesce(
                ovr.staff_compensation_scope, rl.staff_compensation_scope, 'none'
            ) as staff_compensation_scope,
            coalesce(
                ovr.staff_observations_scope, rl.staff_observations_scope, 'none'
            ) as staff_observations_scope,
            coalesce(
                ovr.staff_benefits_scope, rl.staff_benefits_scope, 'none'
            ) as staff_benefits_scope,
        from enriched as e
        left join
            {{ ref("stg_google_sheets__people__cube_access_department_override") }}
            as ovr
            on e.department_name = ovr.department
        left join
            {{ ref("stg_google_sheets__people__cube_access_role") }} as rl
            on e.job_function_code = rl.job_function_code
            and rl.entity in ('any', e.entity)
            and rl.department_type in ('any', e.department_type)
    )

select
    staff_key,
    google_email,
    region_key,
    location_abbreviation,
    department_group,
    department_type,
    entity,
    job_function_code,
    job_function_level,

    student_summary_location_scope,
    student_detail_location_scope,
    student_pii_scope,

    staff_summary_location_scope,
    staff_summary_department_scope,
    staff_detail_location_scope,
    staff_detail_department_scope,
    staff_detail_org_gate,
    staff_pii_scope,
    staff_compensation_scope,
    staff_observations_scope,
    staff_benefits_scope,
from matched
```

Note: the `scoped` CTE (which derived `scope_key`/`scope_level`) is removed —
the viewer's `region_key` / `location_abbreviation` / `department_group` are now
carried verbatim and the location level lives in the scope columns; `cube.js`
builds the filter from level + identity. A `none` location scope on a row whose
`region_key`/`abbreviation` is NULL is harmless (the level is what gates).

- [ ] **Step 2: Rework the model properties**

Replace the `columns:` in `properties/dim_staff_cube_access.yml`. Keep the
`staff_key` PK block (`primary_key` constraint, `unique`, `not_null`,
`relationships` to `ref('dim_staff')`). Replace the access columns with the new
set, each with a `description:` and `accepted_values` (nested under
`arguments:`) matching the staging enums from Task 1 Step 3 (location:
`[network, region, school, none]`; department: `[all, own_group, none]`;
org-gate: `[all_in_scope, below_rank_or_downline, downline_only, none]`; pii/
comp/obs/benefits: `[all, reporting_chain, teaching_staff, none]`; student_pii:
`[all, none]`). Mart tests may stay `severity: warn` (project default). Add
descriptions for `region_key`, `location_abbreviation`, `department_group`,
`department_type`, `entity`, `job_function_code`, `job_function_level`.

- [ ] **Step 3: Verify the exposure already lists both dims**

Run:
`grep -n 'dim_staff_cube_access\|dim_staff_reporting_chain' src/dbt/kipptaf/models/exposures/cube.yml`
Expected: both `ref(...)` lines present (no edit needed; if absent, add them
under `cube_semantic_layer.depends_on`).

- [ ] **Step 4: Build + test the model (after the sheet is staged — see
      Prerequisites)**

Run:
`uv run dbt build --select dim_staff_cube_access --target dev --defer --favor-state --state src/dbt/kipptaf/target/prod --project-dir src/dbt/kipptaf`
Expected: model builds; `unique` / `not_null` / `relationships` /
`accepted_values` tests PASS. If `accepted_values` fails, the sheet has an
out-of-vocabulary value — fix the sheet, re-stage, rebuild.

- [ ] **Step 5: Verify 1:1 grain (no PII in output)**

Run (BigQuery MCP or `bq`, aggregate only):

```sql
select
  count(*) as n_rows,
  count(distinct staff_key) as n_keys,
  countif(staff_detail_org_gate = 'none') as n_no_staff_detail,
from `teamster-332318`.kipptaf_marts.dim_staff_cube_access
```

Expected: `n_rows = n_keys` (1:1); `n_no_staff_detail` is a plausible
default-deny count (do not log any staff identifiers).

- [ ] **Step 6: Lint + commit**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml`
Expected: No issues.

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml
git commit -m "feat(dbt): rework dim_staff_cube_access to two-scope axes"
```

---

### Task 3: Expose `job_function_*` + `department_group` on the `staff` cube

**Files:**

- Modify: `src/cube/model/cubes/staff/staff.yml`

**Interfaces:**

- Consumes: `kipptaf_marts.dim_staff_cube_access` (Task 2).
- Produces: `staff` cube dimensions `staff.job_function_level` (number),
  `staff.job_function_code` (string), `staff.department_group` (string), used as
  viewee-side filter members by `queryRewrite` (Task 7) and exposed on the staff
  views (Task 4).

- [ ] **Step 1: Convert `sql_table` to an inline join `sql:`**

Replace the cube header (lines 1-4) of `staff.yml`:

```yaml
cubes:
  - name: staff
    public: false
    # dim_staff (person grain) enriched with the viewer's CURRENT-role access
    # facts from dim_staff_cube_access (1:1 on staff_key, no fan-out). Only the
    # three org-fact columns the row filters compare against are pulled — never
    # the access-policy columns (see src/cube/CLAUDE.md security model).
    sql: |
      SELECT
        s.*,
        a.job_function_level,
        a.job_function_code,
        a.department_group,
      FROM kipptaf_marts.dim_staff AS s
      LEFT JOIN kipptaf_marts.dim_staff_cube_access AS a
        ON s.staff_key = a.staff_key
```

(The existing `dimensions:` block is unchanged and follows.)

- [ ] **Step 2: Add the three dimensions**

Append to the `dimensions:` list in `staff.yml`:

```yaml
# Current-role access facts from dim_staff_cube_access (viewee-side filter
# members for queryRewrite). NULL for non-active / non-primary staff.
- name: job_function_level
  description: Current org rank (1 = Chief, 6 = Teacher) for row gating.
  sql: job_function_level
  type: number
  public: true

- name: job_function_code
  description: Current ADP job function code for teaching-staff gating.
  sql: job_function_code
  type: string
  public: true

- name: department_group
  description: Current functional department group for department gating.
  sql: department_group
  type: string
  public: true
```

- [ ] **Step 3: Validate the YAML parses**

Run:
`node -e "const yaml=require('js-yaml');yaml.load(require('fs').readFileSync('src/cube/model/cubes/staff/staff.yml','utf8'));console.log('ok')"`
(from a context with `js-yaml`, e.g. `npm --prefix src/cube ls js-yaml`; if
unavailable, skip — Cube Dev Mode in Task 10 validates compilation). Expected:
`ok`.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/cubes/staff/staff.yml
git commit -m "feat(cube): expose job_function_level/code + department_group on staff"
```

---

### Task 4: Staff view tiers + filter members

**Files:**

- Modify: `src/cube/model/views/staff/staff_detail.yml`
- Modify: `src/cube/model/views/staff/staff_summary.yml`

**Interfaces:**

- Consumes: `staff` cube dims from Task 3.
- Produces: `staff_detail` exposing `staff.job_function_level`,
  `job_function_code`, `department_group` + access tiers
  `cube-access-staff-detail` / `cube-access-staff-pii`; `staff_summary` exposing
  `department_group` + tier `cube-access-staff-summary`.

- [ ] **Step 1: Add the filter members to `staff_detail`**

In `staff_detail.yml`, in the `join_path: staff_work_history.staff` includes
block (currently lines 43-62), add three members:

```yaml
- job_function_level
- job_function_code
- department_group
```

(They are queryable members the row filters reference; they need not appear in
`meta.folders`.)

- [ ] **Step 2: Rename `staff_detail` access tiers**

In `staff_detail.yml`, change the `access_policy` block: rename
`cube-access-staff-data` → `cube-access-staff-detail` (keep its
`includes: "*"` + `excludes:` PII list). Keep the `cube-access-staff-pii` block
unchanged.

```yaml
access_policy:
  - group: cube-access-staff-detail
    member_level:
      includes: "*"
      excludes:
        - personal_email
        - personal_cell_phone
        - birth_date
        - gender_identity
        - race
        - is_hispanic
  - group: cube-access-staff-pii
    member_level:
      includes: "*"
```

- [ ] **Step 3: Add `department_group` to `staff_summary` + rename its tier**

In `staff_summary.yml`, add `department_group` to the
`join_path: staff_work_history.staff` includes block (currently lines 40-45),
and rename the access tier `cube-access-staff-data` →
`cube-access-staff-summary`:

```yaml
access_policy:
  - group: cube-access-staff-summary
    member_level:
      includes: "*"
```

- [ ] **Step 4: Lint + commit**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/views/staff/staff_detail.yml src/cube/model/views/staff/staff_summary.yml`
Expected: No issues.

```bash
git add src/cube/model/views/staff/staff_detail.yml src/cube/model/views/staff/staff_summary.yml
git commit -m "feat(cube): staff view detail/summary tiers + filter members"
```

---

### Task 5: Rename student view access tiers

**Files:**

- Modify:
  `src/cube/model/views/student_attendance/student_attendance_detail.yml`
- Modify:
  `src/cube/model/views/student_attendance/student_attendance_summary.yml`
- Modify: `src/cube/model/views/students/student_enrollments_detail.yml`
- Modify: `src/cube/model/views/students/student_enrollments_summary.yml`
- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_detail.yml`
- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_summary.yml`

**Interfaces:**

- Produces: detail views gate on `cube-access-student-detail` (+ existing
  `cube-access-student-pii`); summary views gate on
  `cube-access-student-summary`.

- [ ] **Step 1: Rename the three detail views' base tier**

In each `*_detail.yml`, in the `access_policy` block, rename the group
`cube-access-student-data` → `cube-access-student-detail` (leave its
`member_level.includes: "*"` + `excludes:` list and the
`cube-access-student-pii` block unchanged). Files:
`student_attendance_detail.yml`, `student_enrollments_detail.yml`,
`student_assessment_scores_detail.yml`.

- [ ] **Step 2: Rename the three summary views' tier**

In each `*_summary.yml`, rename the single `access_policy` group
`cube-access-student-data` → `cube-access-student-summary` (keep
`includes: "*"`). Files: `student_attendance_summary.yml`,
`student_enrollments_summary.yml`, `student_assessment_scores_summary.yml`.

- [ ] **Step 3: Verify no stray `cube-access-student-data` remains**

Run: `grep -rn 'cube-access-student-data' src/cube/model/views/` Expected: no
matches.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/student_attendance src/cube/model/views/students src/cube/model/views/student_assessments
git commit -m "feat(cube): split student views into detail/summary access tiers"
```

---

### Task 6: `src/cube/access.js` — pure resolution logic (TDD)

**Files:**

- Create: `src/cube/access.js`
- Create: `src/cube/access.test.js`

**Interfaces:**

- Produces (exported from `access.js`): `isStudentMember(member)`,
  `isStaffMember(member)`, `queryMembers(query)`, `surfaceOf(query)`,
  `buildGroups(row)`, `studentRowFilters(row, surface)`,
  `staffRowFilters(row, reporteeStaffKeys, surface)`,
  `staffColumnNarrowing(query, row, reporteeStaffKeys)`, `STAFF_PII_MEMBERS`,
  `DENY_FILTER`. Consumed by `cube.js` (Task 7).

- [ ] **Step 1: Write the failing tests**

Create `src/cube/access.test.js`:

```javascript
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const a = require("./access");

const SL = {
  region_key: "R1",
  location_abbreviation: "ABC",
  department_group: "Ops",
  job_function_level: 4,
  student_summary_location_scope: "network",
  student_detail_location_scope: "school",
  student_pii_scope: "all",
  staff_summary_location_scope: "network",
  staff_summary_department_scope: "all",
  staff_detail_location_scope: "school",
  staff_detail_department_scope: "all",
  staff_detail_org_gate: "below_rank_or_downline",
  staff_pii_scope: "all",
  staff_compensation_scope: "none",
  staff_observations_scope: "none",
  staff_benefits_scope: "none",
};

test("surfaceOf reads the view suffix", () => {
  assert.equal(
    a.surfaceOf({ dimensions: ["staff_detail.full_name"] }),
    "detail",
  );
  assert.equal(
    a.surfaceOf({ measures: ["staff_summary.count_employees"] }),
    "summary",
  );
  assert.equal(a.surfaceOf({ dimensions: ["dates.date_day"] }), null);
});

test("buildGroups: SL gets detail+summary+pii for both domains", () => {
  const g = a.buildGroups(SL);
  assert.ok(g.includes("cube-access-student-detail"));
  assert.ok(g.includes("cube-access-student-summary"));
  assert.ok(g.includes("cube-access-student-pii"));
  assert.ok(g.includes("cube-access-staff-detail"));
  assert.ok(g.includes("cube-access-staff-summary"));
  assert.ok(g.includes("cube-access-staff-pii"));
});

test("buildGroups: summary-only student viewer gets no student-detail", () => {
  const g = a.buildGroups({
    ...SL,
    student_detail_location_scope: "none",
    student_pii_scope: "none",
  });
  assert.ok(g.includes("cube-access-student-summary"));
  assert.ok(!g.includes("cube-access-student-detail"));
  assert.ok(!g.includes("cube-access-student-pii"));
});

test("buildGroups: null row → no groups", () => {
  assert.deepEqual(a.buildGroups(null), []);
});

test("studentRowFilters: detail=school → abbreviation filter", () => {
  const f = a.studentRowFilters(SL, "detail");
  assert.deepEqual(f, [
    { member: "locations.abbreviation", operator: "equals", values: ["ABC"] },
  ]);
});

test("studentRowFilters: summary=network → no filter", () => {
  assert.deepEqual(a.studentRowFilters(SL, "summary"), []);
});

test("studentRowFilters: none → deny", () => {
  const f = a.studentRowFilters(
    { ...SL, student_detail_location_scope: "none" },
    "detail",
  );
  assert.deepEqual(f, [a.DENY_FILTER]);
});

test("staffRowFilters summary: network ∩ all-dept → no filter", () => {
  assert.deepEqual(a.staffRowFilters(SL, [], "summary"), []);
});

test("staffRowFilters detail below_rank_or_downline: OR(scope∧rank, downline)", () => {
  const f = a.staffRowFilters(SL, ["k1", "k2"], "detail");
  assert.equal(f.length, 1);
  assert.ok(f[0].or, "top-level OR");
  const [scope, downline] = f[0].or;
  assert.ok(scope.and.some((c) => c.member === "locations.abbreviation"));
  assert.ok(
    scope.and.some(
      (c) =>
        c.member === "staff.job_function_level" &&
        c.operator === "gt" &&
        c.values[0] === "4",
    ),
  );
  assert.deepEqual(downline, {
    member: "staff.staff_key",
    operator: "equals",
    values: ["k1", "k2"],
  });
});

test("staffRowFilters detail downline_only: just the downline IN", () => {
  const f = a.staffRowFilters(
    { ...SL, staff_detail_org_gate: "downline_only" },
    ["k1"],
    "detail",
  );
  assert.deepEqual(f, [
    { member: "staff.staff_key", operator: "equals", values: ["k1"] },
  ]);
});

test("staffRowFilters detail all_in_scope + network → no filter (all in scope)", () => {
  const exec = {
    ...SL,
    staff_detail_org_gate: "all_in_scope",
    staff_detail_location_scope: "network",
    staff_detail_department_scope: "all",
  };
  assert.deepEqual(a.staffRowFilters(exec, [], "detail"), []);
});

test("staffRowFilters detail org_gate none → deny", () => {
  assert.deepEqual(
    a.staffRowFilters({ ...SL, staff_detail_org_gate: "none" }, [], "detail"),
    [a.DENY_FILTER],
  );
});

test("staffColumnNarrowing: reporting_chain PII request narrows to downline", () => {
  const row = { ...SL, staff_pii_scope: "reporting_chain" };
  const q = { dimensions: ["staff_detail.personal_email"] };
  const f = a.staffColumnNarrowing(q, row, ["k1"]);
  assert.deepEqual(f, [
    { member: "staff.staff_key", operator: "equals", values: ["k1"] },
  ]);
});

test("staffColumnNarrowing: teaching_staff PII request narrows to TEACH/TIR", () => {
  const row = { ...SL, staff_pii_scope: "teaching_staff" };
  const q = { dimensions: ["staff_detail.race"] };
  const f = a.staffColumnNarrowing(q, row, []);
  assert.deepEqual(f, [
    {
      member: "staff.job_function_code",
      operator: "equals",
      values: ["TEACH", "TIR"],
    },
  ]);
});

test("staffColumnNarrowing: pii_scope=all → no extra filter", () => {
  const q = { dimensions: ["staff_detail.personal_email"] };
  assert.deepEqual(a.staffColumnNarrowing(q, SL, ["k1"]), []);
});
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `node --test src/cube/access.test.js` Expected: FAIL —
`Cannot find module './access'`.

- [ ] **Step 3: Implement `access.js`**

Create `src/cube/access.js`:

```javascript
"use strict";

// Pure access-resolution helpers for cube.js. No I/O — unit-tested with
// `node --test src/cube/access.test.js`. cube.js owns the BigQuery reads +
// cache and calls these to translate a cached access row into Cube groups and
// per-surface query filters. See docs/superpowers/specs/2026-06-03-cube-security-redesign.md.

// A query member is "<view>.<member>"; the domain is the leading token.
const isStudentMember = (member) => member.startsWith("student");
const isStaffMember = (member) => member.startsWith("staff");

// Default-deny: an empty IN () matches no rows. Routed through the locations
// join present on every view.
const DENY_FILTER = {
  member: "locations.abbreviation",
  operator: "equals",
  values: [],
};

// Staff PII members gated by staff_pii_scope (the only sensitive staff columns
// in v1; comp/observation members slot in here when those cubes are built).
const STAFF_PII_MEMBERS = [
  "personal_email",
  "personal_cell_phone",
  "birth_date",
  "gender_identity",
  "race",
  "is_hispanic",
];

function queryMembers(query) {
  return [
    ...(query.dimensions ?? []),
    ...(query.measures ?? []),
    ...(query.timeDimensions ?? []).map((td) => td.dimension).filter(Boolean),
    ...(query.filters ?? []).map((f) => f.member).filter(Boolean),
  ];
}

// "detail" | "summary" | null — by the view-name suffix on the query's members.
function surfaceOf(query) {
  for (const m of queryMembers(query)) {
    const view = m.split(".")[0];
    if (view.endsWith("_detail")) return "detail";
    if (view.endsWith("_summary")) return "summary";
  }
  return null;
}

// Column-visibility tiers the views gate on. One student + one staff tier set.
function buildGroups(row) {
  if (!row) return [];
  const groups = [];

  if (row.student_detail_location_scope !== "none") {
    groups.push("cube-access-student-detail", "cube-access-student-summary");
  } else if (row.student_summary_location_scope !== "none") {
    groups.push("cube-access-student-summary");
  }
  if (row.student_pii_scope === "all") groups.push("cube-access-student-pii");

  // Staff detail exists whenever the org gate grants anything (the downline is
  // unioned regardless of location, so even a no-location manager sees detail).
  if (row.staff_detail_org_gate && row.staff_detail_org_gate !== "none") {
    groups.push("cube-access-staff-detail", "cube-access-staff-summary");
  } else if (row.staff_summary_location_scope !== "none") {
    groups.push("cube-access-staff-summary");
  }
  if (row.staff_pii_scope && row.staff_pii_scope !== "none") {
    groups.push("cube-access-staff-pii");
  }
  return groups;
}

// { filter } (push it) | { open: true } (no filter) | { deny: true } (none).
function locationScopeFilter(level, regionKey, abbreviation) {
  switch (level) {
    case "network":
      return { open: true };
    case "region":
      return {
        filter: {
          member: "locations.region_key",
          operator: "equals",
          values: [regionKey],
        },
      };
    case "school":
      return {
        filter: {
          member: "locations.abbreviation",
          operator: "equals",
          values: [abbreviation],
        },
      };
    default:
      return { deny: true };
  }
}

function departmentScopeFilter(scope, departmentGroup) {
  if (scope === "all") return { open: true };
  if (scope === "own_group")
    return {
      filter: {
        member: "staff.department_group",
        operator: "equals",
        values: [departmentGroup],
      },
    };
  return { deny: true };
}

function studentRowFilters(row, surface) {
  if (!row) return [DENY_FILTER];
  const level =
    surface === "detail"
      ? row.student_detail_location_scope
      : row.student_summary_location_scope;
  const loc = locationScopeFilter(
    level,
    row.region_key,
    row.location_abbreviation,
  );
  if (loc.deny) return [DENY_FILTER];
  return loc.open ? [] : [loc.filter];
}

function staffSummaryFilters(row) {
  const loc = locationScopeFilter(
    row.staff_summary_location_scope,
    row.region_key,
    row.location_abbreviation,
  );
  const dep = departmentScopeFilter(
    row.staff_summary_department_scope,
    row.department_group,
  );
  if (loc.deny || dep.deny) return [DENY_FILTER];
  const filters = [];
  if (!loc.open) filters.push(loc.filter);
  if (!dep.open) filters.push(dep.filter);
  return filters;
}

function staffDetailFilters(row, reporteeStaffKeys) {
  const gate = row.staff_detail_org_gate;
  const includeScope =
    gate === "all_in_scope" || gate === "below_rank_or_downline";
  const includeDownline =
    gate === "downline_only" || gate === "below_rank_or_downline";
  const branches = [];

  if (includeScope) {
    const loc = locationScopeFilter(
      row.staff_detail_location_scope,
      row.region_key,
      row.location_abbreviation,
    );
    const dep = departmentScopeFilter(
      row.staff_detail_department_scope,
      row.department_group,
    );
    if (!loc.deny && !dep.deny) {
      const and = [];
      if (!loc.open) and.push(loc.filter);
      if (!dep.open) and.push(dep.filter);
      if (gate === "below_rank_or_downline") {
        and.push({
          member: "staff.job_function_level",
          operator: "gt",
          values: [String(row.job_function_level)],
        });
      }
      // Unrestricted scope (e.g. all_in_scope + network + all-dept) → all rows.
      if (and.length === 0) return [];
      branches.push(and.length === 1 ? and[0] : { and });
    }
  }

  if (includeDownline && reporteeStaffKeys.length) {
    branches.push({
      member: "staff.staff_key",
      operator: "equals",
      values: reporteeStaffKeys,
    });
  }

  if (branches.length === 0) return [DENY_FILTER];
  if (branches.length === 1) return [branches[0]];
  return [{ or: branches }];
}

function staffRowFilters(row, reporteeStaffKeys, surface) {
  if (!row) return [DENY_FILTER];
  return surface === "detail"
    ? staffDetailFilters(row, reporteeStaffKeys ?? [])
    : staffSummaryFilters(row);
}

// Row-conditional column visibility: when a sensitive staff column scoped to
// reporting_chain / teaching_staff is requested, narrow the query's rows.
function staffColumnNarrowing(query, row, reporteeStaffKeys) {
  if (!row) return [];
  const requestsPii = queryMembers(query).some((m) =>
    STAFF_PII_MEMBERS.includes(m.split(".").pop()),
  );
  if (!requestsPii) return [];
  if (row.staff_pii_scope === "reporting_chain") {
    return (reporteeStaffKeys ?? []).length
      ? [
          {
            member: "staff.staff_key",
            operator: "equals",
            values: reporteeStaffKeys,
          },
        ]
      : [DENY_FILTER];
  }
  if (row.staff_pii_scope === "teaching_staff") {
    return [
      {
        member: "staff.job_function_code",
        operator: "equals",
        values: ["TEACH", "TIR"],
      },
    ];
  }
  return [];
}

module.exports = {
  isStudentMember,
  isStaffMember,
  queryMembers,
  surfaceOf,
  buildGroups,
  studentRowFilters,
  staffRowFilters,
  staffColumnNarrowing,
  STAFF_PII_MEMBERS,
  DENY_FILTER,
};
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `node --test src/cube/access.test.js` Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cube/access.js src/cube/access.test.js
git commit -m "feat(cube): add tested access-resolution module"
```

---

### Task 7: Rewrite `cube.js` — BigQuery `contextToGroups` + composed `queryRewrite`

**Files:**

- Modify: `src/cube/cube.js`

**Interfaces:**

- Consumes: `access.js` (Task 6), `dim_staff_cube_access` (Task 2),
  `dim_staff_reporting_chain`.
- Produces: the running access enforcement. Removes the `googleapis` Directory
  API path.

- [ ] **Step 1: Require `access.js` and replace `isStudentMember`**

At the top of `cube.js`, after `const groupCache = ...`, add:

```javascript
const access = require("./access");
```

Delete the local `const isStudentMember = ...` definition (lines ~23-31) — it
now comes from `access`. Leave `nextMidnightEastern` and the `SNAPSHOT_*`
constants unchanged.

- [ ] **Step 2: Rewrite `contextToGroups`**

Replace the entire `contextToGroups` function with the BigQuery version. It
caches `{ groups, row, reporteeStaffKeys, expiresAt }`:

```javascript
  contextToGroups: async ({ securityContext }) => {
    const email =
      securityContext?.email ??
      securityContext?.cubeCloud?.userAttributes?.email;
    if (!email) return [];

    // Local dev only: CUBE_GROUP_MAP bypasses BigQuery. Never set in Cloud.
    if (process.env.NODE_ENV !== "production" && process.env.CUBE_GROUP_MAP) {
      try {
        const map = JSON.parse(process.env.CUBE_GROUP_MAP);
        const groups = (map[email] ?? []).filter((g) => g.startsWith("cube-"));
        groupCache.set(email, { groups, row: null, reporteeStaffKeys: [], expiresAt: nextMidnightEastern() });
        return groups;
      } catch (err) {
        console.error("CUBE_GROUP_MAP is not valid JSON:", err.message);
        return [];
      }
    }

    const cached = groupCache.get(email);
    if (cached && cached.expiresAt > Date.now()) return cached.groups;

    try {
      const { BigQuery } = require("@google-cloud/bigquery");
      const bq = new BigQuery();

      // 1. email → access row (active+primary row only).
      const [accessRows] = await bq.query({
        query: `
          SELECT
            staff_key, region_key, location_abbreviation, department_group,
            job_function_level,
            student_summary_location_scope, student_detail_location_scope,
            student_pii_scope,
            staff_summary_location_scope, staff_summary_department_scope,
            staff_detail_location_scope, staff_detail_department_scope,
            staff_detail_org_gate, staff_pii_scope,
            staff_compensation_scope, staff_observations_scope,
            staff_benefits_scope
          FROM kipptaf_marts.dim_staff_cube_access
          WHERE google_email = @email
          LIMIT 1`,
        params: { email },
      });
      const row = accessRows[0] ?? null;

      // 2. reporting chain keyed on the resolved staff_key.
      let reporteeStaffKeys = [];
      if (row?.staff_key) {
        const [reporteeRows] = await bq.query({
          query: `
            SELECT reportee_staff_key
            FROM kipptaf_marts.dim_staff_reporting_chain
            WHERE manager_staff_key = @staffKey`,
          params: { staffKey: row.staff_key },
        });
        reporteeStaffKeys = reporteeRows.map((r) => r.reportee_staff_key);
      }

      const groups = access.buildGroups(row);
      groupCache.set(email, { groups, row, reporteeStaffKeys, expiresAt: nextMidnightEastern() });
      return groups;
    } catch (err) {
      console.error(`contextToGroups failed for ${email}:`, err);
      return []; // default deny on failure
    }
  },
```

- [ ] **Step 3: Rewrite the row-gating head of `queryRewrite`**

Replace the top of `queryRewrite` (from the `const email = ...` line through the
location-scope block that ends before the snapshot guard — current lines
~154-214) with the composed version. Keep everything from
`// Snapshot anchor guard` onward unchanged, operating on the `filters` array
defined here:

```javascript
  queryRewrite: (query, { securityContext }) => {
    const email =
      securityContext?.email ??
      securityContext?.cubeCloud?.userAttributes?.email;
    const cached = email ? groupCache.get(email) : null;
    const fresh = cached && cached.expiresAt > Date.now() ? cached : null;
    const row = fresh?.row ?? null;
    const reporteeStaffKeys = fresh?.reporteeStaffKeys ?? [];
    const groups = fresh?.groups ?? [];

    // Strip student members entirely when the viewer has no student access.
    const hasStudentAccess =
      groups.includes("cube-access-student-detail") ||
      groups.includes("cube-access-student-summary");
    if (!hasStudentAccess) {
      query = {
        ...query,
        dimensions: (query.dimensions ?? []).filter((d) => !access.isStudentMember(d)),
        measures: (query.measures ?? []).filter((m) => !access.isStudentMember(m)),
      };
    }

    const members = access.queryMembers(query);
    const surface = access.surfaceOf(query);
    const filters = [...(query.filters ?? [])];

    if (members.some(access.isStudentMember)) {
      filters.push(...access.studentRowFilters(row, surface));
    }
    if (members.some(access.isStaffMember)) {
      filters.push(...access.staffRowFilters(row, reporteeStaffKeys, surface));
      if (surface === "detail") {
        filters.push(...access.staffColumnNarrowing(query, row, reporteeStaffKeys));
      }
    }

    // ... existing snapshot anchor guard, operating on `filters`, unchanged ...

    return { ...query, filters };
  },
```

Note: the snapshot guard block (the `for (const cubePrefix of SNAPSHOT_CUBES)`
loop and its helpers) is preserved verbatim between the filter-push block and
`return { ...query, filters }`.

- [ ] **Step 4: Verify the access tests still pass + cube.js loads**

Run: `node --test src/cube/access.test.js` Expected: PASS (access.js unchanged).

Run:
`node -e "process.env.NODE_ENV='test';require('./src/cube/cube.js');console.log('loaded')"`
Expected: `loaded` (module requires cleanly; BigQuery is lazily required inside
`contextToGroups`, so no credentials are needed to load).

- [ ] **Step 5: Commit**

```bash
git add src/cube/cube.js
git commit -m "feat(cube): BigQuery contextToGroups + two-scope queryRewrite"
```

---

### Task 8: Cube schema test — no `dim_`/`fct_` cube names

**Files:**

- Create: `tests/cube/test_cube_schema.py`

**Interfaces:**

- Consumes: `src/cube/model/**/*.yml`.

- [ ] **Step 1: Write the test**

Create `tests/cube/test_cube_schema.py`:

```python
"""Cube schema invariants — cube/view names carry no warehouse prefix."""

import pathlib

import yaml

CUBE_MODEL_DIR = pathlib.Path(__file__).parents[2] / "src" / "cube" / "model"


def _names() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in CUBE_MODEL_DIR.rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for kind in ("cubes", "views"):
            for obj in doc.get(kind, []) or []:
                found.append((str(path), obj["name"]))
    return found


def test_no_dim_or_fct_prefix_on_cube_names() -> None:
    offenders = [
        f"{path}: {name}"
        for path, name in _names()
        if name.startswith(("dim_", "fct_"))
    ]
    assert not offenders, "cube/view names must not carry a dim_/fct_ prefix:\n" + "\n".join(offenders)


def test_model_dir_has_cubes() -> None:
    # Guard against a path regression silently passing the prefix test.
    assert _names(), f"no cubes/views found under {CUBE_MODEL_DIR}"
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/cube/test_cube_schema.py -v` Expected: both tests PASS
(cube names are already clean on `main`).

- [ ] **Step 3: Commit**

```bash
git add tests/cube/test_cube_schema.py
git commit -m "test(cube): assert no dim_/fct_ prefix on cube names"
```

---

### Task 9: Documentation

**Files:**

- Modify: `src/cube/CLAUDE.md` (`## cube.js security model` +
  `## View access policies` sections)
- Modify: `src/cube/model/views/staff/staff_detail.yml` (description note)
- Modify: `docs/guides/cube.md` if it documents the Directory API path

**Interfaces:** none (docs).

- [ ] **Step 1: Update `src/cube/CLAUDE.md` security model**

In `## cube.js security model`, replace the `contextToGroups` Directory-API
bullet and the `queryRewrite` bullets to describe: BigQuery reads of
`dim_staff_cube_access` (by `google_email`) + `dim_staff_reporting_chain` (by
`manager_staff_key`), cached to midnight ET; pure resolution in
`src/cube/access.js`; `queryRewrite` branching on the view surface
(detail/summary) and applying location ∩ department ∩ org-gate ∪ downline; the
`staff` cube's `dim_staff_cube_access` join for `job_function_level` /
`job_function_code` / `department_group`; `isStaffMember`. Update
`## View access policies` to the `-detail` / `-summary` / `-pii` tier names and
note the reporting-chain gate (the #4092 deliverable).

- [ ] **Step 2: Document the gate in `staff_detail.yml`**

Add a sentence to the `staff_detail` `description:` noting that row visibility
is gated by the viewer's detail scope and reporting chain (per
`dim_staff_cube_access`), and that requesting a `reporting_chain`-scoped PII
column narrows results to the viewer's downline.

- [ ] **Step 3: Lint + commit**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force src/cube/CLAUDE.md src/cube/model/views/staff/staff_detail.yml docs/guides/cube.md`
Expected: No issues.

```bash
git add src/cube/CLAUDE.md src/cube/model/views/staff/staff_detail.yml docs/guides/cube.md
git commit -m "docs(cube): document two-scope access model + reporting-chain gate"
```

---

### Task 10: Validation & rollout (handoff — needs the user's environment)

**Files:** none (operational).

These steps require Cube Cloud Dev Mode, production deploy, and Google Workspace
admin — they are NOT agent-codeable. Hand off to the user with this checklist.

- [ ] **Step 1: Stage the crosswalks** — confirm the data team filled the new
      sheet columns and the externals are re-staged (Prerequisites). Rebuild
      `dim_staff_cube_access` and re-run Task 2 Step 4–5.

- [ ] **Step 2: Cube Dev Mode validation** — push the branch; in Cube Cloud →
      Data Model → Dev Mode, add the branch. With test emails per tier, confirm:
  - network/region/school **summary** breadth vs **detail** breadth differ as
    configured (e.g. SL: network summary, school detail);
  - a manager sees their **downline at detail even across schools** (the union);
  - same-level non-reports are hidden at detail;
  - special-access department sees all in scope at detail;
  - no-access viewer is denied (`WHERE (1 = 0)` / empty `IN ()`);
  - a `pii` viewer sees PII columns; a `reporting_chain` PII request narrows
    rows to the downline. Verify `GOOGLE_*` secrets are NOT required anymore
    (Directory API removed).

- [ ] **Step 3: Deploy** — merge to `main` (Cube Cloud redeploys on merge).
      Spot-check each tier in production over one full school day.

- [ ] **Step 4: Retire `cube-*` Google Workspace groups** — once validated, the
      groups are unused (names are now internal). Remove them.

- [ ] **Step 5: Data-quality follow-up** — confirm #4260 tracks staff whose
      current assignment can't resolve a role (aggregate counts only, no PII).

---

## Self-Review

- **Spec coverage:** Three axes + summary/detail independence → Tasks 1–2
  (schema), 6–7 (logic). `detail = scope ∪ downline` → Task 6
  `staffDetailFilters`
  - Task 7. Decomposed location/department → Tasks 1–2, 6. Staff-cube join for
    `job_function_level`/`code`/`department_group` → Task 3. View tier renames →
    Tasks 4–5. `contextToGroups` BigQuery + no Directory API → Task 7. Schema
    test → Task 8. Docs/#4092 → Task 9. Crosswalk re-fill, Dev-Mode validation,
    group retirement, #4260 → Prerequisites + Task 10. Forward-compat comp/obs →
    Task 6 `STAFF_PII_MEMBERS` comment + `staffColumnNarrowing` (slot-in point).
- **Type consistency:** `buildGroups` / `studentRowFilters` / `staffRowFilters`
  / `staffColumnNarrowing` / `DENY_FILTER` / `surfaceOf` / `queryMembers` /
  `isStudentMember` / `isStaffMember` names match between `access.js` (Task 6),
  its tests, and `cube.js` (Task 7). Filter members (`locations.region_key`,
  `locations.abbreviation`, `staff.staff_key`, `staff.job_function_level`,
  `staff.job_function_code`, `staff.department_group`) match the dimensions
  exposed in Tasks 3–4. Column names match across Task 1 (source) → Task 2 (dim)
  → Task 7 (query).
- **Placeholders:** none — every code step carries complete content.
