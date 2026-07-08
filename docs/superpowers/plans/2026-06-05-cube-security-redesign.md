# Cube Security Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Cube's Google-Group-based access control with two HR-derived
dbt models (`dim_staff_reporting_chain`, `dim_staff_cube_access`) and a
rewritten `cube.js` that resolves scope, reporting-chain, and field visibility
from BigQuery at request time.

**Architecture:** Two new marts read `int_people__staff_roster` (documented
exception to the no-ref-up-into-int rule). `dim_staff_cube_access` resolves one
row per active staff member (keyed on `staff_key`) to scope + access tiers +
field-visibility scopes via a department special-access override layered over a
role-based CASE. `dim_staff_reporting_chain` is the transitive closure of the
org tree. `cube.js` `contextToGroups` resolves the JWT email → `staff_key` +
access row + reportee set (cached to midnight ET); `queryRewrite` injects
location, reporting-chain, and field-scope row filters. Staff cubes/views follow
the existing attendance detail/summary pattern.

**Tech Stack:** dbt (BigQuery), Cube (`cube.js` + YAML), Python (pytest),
`@google-cloud/bigquery` Node driver.

**Source of truth for mappings:** the
[job groupings explorer](https://teamschools.github.io/job_groupings/website/explorer.html)
and the two mapping tables in the spec
([2026-06-03-cube-security-redesign.md](../specs/2026-06-03-cube-security-redesign.md)).

---

## Prerequisites and sequencing

**BLOCKER — `job_function_code`:** `int_people__staff_roster` does not yet carry
`job_function_code` / `job_function_name` (expected end of day 2026-06-05).
Tasks 3+ depend on it. Before starting Task 3, verify:

```bash
uv run dbt show --inline \
  "select job_function_code, count(*) n from {{ ref('int_people__staff_roster') }} group by 1" \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: a small set of codes matching
`CHIEF / EDHOS / SL / DSO / ASL / DEAN / SCOPS / NINST / TEACH / TIR / MGDIR / DIR / KTRGS`.
If the column is missing or the codes differ, STOP and resolve with the
staff-pipeline owner — the CASE statements key on these exact values.

**Department rollup (`department_group`):** the rollup from
`assigned_department_name` (43 values) into department groups is owned by the
data team. Task 4 ships a CASE skeleton covering the 8 special-access
departments and a documented `else` fallback; the data team fills the remaining
groups before production. This does not block building/testing the model.

**Dev-schema testing pattern (Cube):** cube YAML referencing not-yet-merged mart
columns errors in the playground. Per `src/cube/CLAUDE.md`, build the mart into
your dev schema and temporarily repoint `sql_table` to
`zz_<username>_kipptaf_marts.<table>` for local `npm run dev` testing; revert
before commit.

**Order of phases:**

1. Phase A — `dim_staff_reporting_chain` (Tasks 1–2). Independent of
   `job_function_code`; can start immediately.
2. Phase B — `dim_staff_cube_access` (Tasks 3–5). Needs `job_function_code`.
3. Phase C — cube schema test + renames (Tasks 6–7). Independent; can be done
   anytime.
4. Phase D — staff cubes/views (Tasks 8–9). Needs Phase B merged to prod (cube
   reads `kipptaf_marts`).
5. Phase E — `cube.js` rewrite (Tasks 10–13). Needs Phases A+B in prod.
6. Phase F — validation + group retirement (Tasks 14–15).

---

## File structure

| File                                                                    | Responsibility                                |
| ----------------------------------------------------------------------- | --------------------------------------------- |
| `src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql` | Org-tree transitive closure                   |
| `.../dimensions/properties/dim_staff_reporting_chain.yml`               | Contract, tests, descriptions                 |
| `.../dimensions/dim_staff_cube_access.sql`                              | One access row per staff member               |
| `.../dimensions/properties/dim_staff_cube_access.yml`                   | Contract, tests, descriptions                 |
| `tests/cube/test_cube_schema.py`                                        | CI guard: no `dim_`/`fct_` cube-name prefixes |
| `src/cube/model/cubes/staff/staff.yml`                                  | Staff cube (renamed from `dim_staff`)         |
| `src/cube/model/views/staff/staff_detail.yml`                           | Row-level staff view                          |
| `src/cube/model/views/staff/staff_summary.yml`                          | Aggregate staff view                          |
| `src/cube/cube.js`                                                      | `contextToGroups` + `queryRewrite` rewrite    |

---

## Phase A — `dim_staff_reporting_chain`

### Task 1: Reporting-chain model + recursive closure

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql`

The chain is the transitive closure of
`reports_to_employee_number → employee_number` over active primary roster rows,
then both sides hashed to `staff_key` (single-input `generate_surrogate_key`,
matching `dim_staff`). Self-pair (`depth = 0`) included so one `IN (...)` filter
lets a manager see their own row.

- [ ] **Step 1: Write the model SQL**

Create the file with:

```sql
-- Access-control infrastructure model. Reads int_people__staff_roster directly
-- (documented exception to the no-ref-up-into-int marts rule) because the roster
-- is the only source carrying the reports_to edge at active-primary grain.
with
    staff as (
        select
            employee_number,
            reports_to_employee_number,
        from {{ ref("int_people__staff_roster") }}
        where
            worker_status_code != 'Terminated'
            and primary_indicator = true
            and employee_number is not null
    ),

    edges as (
        select distinct
            employee_number as reportee_employee_number,
            reports_to_employee_number as manager_employee_number,
        from staff
        where reports_to_employee_number is not null
    ),

    closure as (
        -- self-pair: a manager is in their own downline at depth 0
        select
            employee_number as manager_employee_number,
            employee_number as reportee_employee_number,
            0 as depth,
        from staff

        union all

        select
            c.manager_employee_number,
            e.reportee_employee_number,
            c.depth + 1 as depth,
        from closure as c
        inner join edges as e
            on c.reportee_employee_number = e.manager_employee_number
        where c.depth < 20  -- cycle backstop; data is a clean tree (max depth 7)
    ),

    deduped as (
        select
            manager_employee_number,
            reportee_employee_number,
            min(depth) as depth,
        from closure
        group by manager_employee_number, reportee_employee_number
    )

select
    {{ dbt_utils.generate_surrogate_key(["manager_employee_number"]) }}
    as manager_staff_key,

    {{ dbt_utils.generate_surrogate_key(["reportee_employee_number"]) }}
    as reportee_staff_key,

    depth,
from deduped
```

Note: the model uses `with recursive`. dbt does not inject the `recursive`
keyword — add it manually. Change the opening to `with recursive` (see Step 2).

- [ ] **Step 2: Fix the recursive keyword**

BigQuery requires `WITH RECURSIVE` when any CTE self-references. Edit the first
line from `with` to:

```sql
with recursive
```

(See `int_illuminate__root_standards.sql` for the in-repo precedent.)

- [ ] **Step 3: Build the model**

Run:

```bash
uv run dbt run --select dim_staff_reporting_chain \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: success, builds `dim_staff_reporting_chain` in your dev schema (or
prod per target). If it errors `Table "closure" must be qualified` → the
`recursive` keyword is missing (redo Step 2).

- [ ] **Step 4: Verify shape**

Run:

```bash
uv run dbt show --inline \
  "select count(*) n_pairs, max(depth) max_depth, countif(depth=0) n_self from {{ ref('dim_staff_reporting_chain') }}" \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: `n_pairs ≈ 7005` (plus self-pairs ≈ +1490, so ~8495 total),
`max_depth ≈ 7`, `n_self ≈ 1490`. If `max_depth = 20`, a cycle exists — STOP and
investigate the roster `reports_to` data.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql
git commit -m "feat(dbt): add dim_staff_reporting_chain org-tree closure"
```

### Task 2: Reporting-chain properties + tests

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_chain.yml`

- [ ] **Step 1: Write the properties YAML**

```yaml
models:
  - name: dim_staff_reporting_chain
    description: >-
      Transitive closure of the staff org tree, for Cube access control. One row
      per (manager, reportee) pair — every staff member who reports up through a
      given manager at any depth, plus a self-pair at depth 0. Keyed on
      staff_key (surrogate of employee_number) so it joins to dim_staff and is
      stable against Google email reuse. Built from int_people__staff_roster's
      reports_to edge over active primary assignments. Rebuilt nightly; role
      changes propagate automatically.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - manager_staff_key
              - reportee_staff_key
    columns:
      - name: manager_staff_key
        data_type: string
        description: >-
          A staff member at or above the reportee in the org tree. FK-style
          reference to dim_staff.staff_key; surrogate of the manager's
          employee_number.
      - name: reportee_staff_key
        data_type: string
        description: >-
          The direct or indirect report. Surrogate of the reportee's
          employee_number. Equals manager_staff_key on the depth-0 self-pair.
      - name: depth
        data_type: int64
        description: >-
          Hops from manager to reportee. 0 = self, 1 = direct report, higher =
          indirect. Minimum hop count if multiple paths exist.
```

- [ ] **Step 2: Parse to validate YAML binds**

Run:

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --target prod
```

Expected: no errors.

- [ ] **Step 3: Run the uniqueness test**

Run:

```bash
uv run dbt test --select dim_staff_reporting_chain \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: PASS. A uniqueness failure means a cycle produced duplicate (manager,
reportee) pairs at different min-depths — should not happen after the
`min(depth)` group-by, but if it does, investigate roster data.

- [ ] **Step 4: trunk check**

Run (from repo root, files must exist):

```bash
.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_chain.yml
```

Expected: no issues (sqlfluff + yamllint clean).

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_chain.yml
git commit -m "feat(dbt): add dim_staff_reporting_chain properties and tests"
```

---

## Phase B — `dim_staff_cube_access`

> **Gate:** confirm `job_function_code` exists (see Prerequisites) before
> starting.

### Task 3: Access model — base roster CTE + staff_key + lookup columns

**Files:**

- Create: `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql`

Build incrementally: this task lays down the source CTE and the non-derived
columns (`staff_key`, `google_email`, `job_function_code`, `job_function_level`,
`entity`, `department_type`, `department_group`). Tasks 4–5 add the access
CASEs.

- [ ] **Step 1: Write the base model**

```sql
-- Access-control infrastructure model. Reads int_people__staff_roster directly
-- (documented exception to the no-ref-up-into-int marts rule). One row per
-- active primary staff member, keyed on staff_key. Resolves each person to the
-- Cube access grants in docs/superpowers/specs/2026-06-03-cube-security-redesign.md.
with
    roster as (
        select
            employee_number,
            google_email,
            job_function_code,
            entity,
            assigned_department_name,
        from {{ ref("int_people__staff_roster") }}
        where
            worker_status_code != 'Terminated'
            and primary_indicator = true
            and employee_number is not null
    ),

    derived as (
        select
            employee_number,
            google_email,
            job_function_code,
            entity,
            assigned_department_name,

            case
                when job_function_code = 'CHIEF' then 1
                when job_function_code = 'EDHOS' then 2
                when job_function_code = 'MGDIR' then 3
                when job_function_code in ('SL', 'DSO', 'DIR') then 4
                when job_function_code in ('ASL', 'KTRGS') then 5
                when job_function_code in (
                    'DEAN', 'SCOPS', 'NINST', 'TEACH', 'TIR'
                ) then 6
                else 99
            end as job_function_level,

            -- TODO(data-team): complete the department_group rollup across all
            -- 43 assigned_department_name values. Skeleton covers the
            -- special-access departments; all others fall to 'other' for now.
            case
                when assigned_department_name in (
                    'Executive', 'Data', 'Human Resources',
                    'Leadership Development', 'Teacher Development',
                    'Accounting', 'Finance', 'Compliance'
                ) then assigned_department_name
                else 'other'
            end as department_group,

            -- TODO(data-team): confirm the instructional / non-instructional
            -- split rule with the staff-data pipeline owner.
            case
                when assigned_department_name in (
                    'Accounting', 'Finance', 'Compliance', 'Human Resources'
                ) then 'non-instructional'
                else 'instructional'
            end as department_type,
        from roster
    )

select
    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as staff_key,

    google_email,
    job_function_code,
    job_function_level,
    entity,
    department_group,
    department_type,
from derived
```

- [ ] **Step 2: Build it**

Run:

```bash
uv run dbt run --select dim_staff_cube_access \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: success. If it errors `Name job_function_code not found` → the roster
column isn't merged yet (see Prerequisites BLOCKER).

- [ ] **Step 3: Verify grain (one row per email/staff_key)**

Run:

```bash
uv run dbt show --inline \
  "select count(*) n, count(distinct staff_key) n_keys, count(distinct google_email) n_email, countif(job_function_level=99) n_unmapped from {{ ref('dim_staff_cube_access') }}" \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: `n == n_keys` (1:1 on staff_key), `n ≈ 1490`. `n_unmapped` should be 0
— if not, a `job_function_code` value is missing from the level CASE; add it.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql
git commit -m "feat(dbt): add dim_staff_cube_access base (staff_key, level, dept)"
```

### Task 4: Access model — role-based scope + access-level CASEs

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql`

Add the role-based mapping: `scope_level`, `scope_key`, `student_access_level`,
`staff_access_level`, and the `*_scope` columns, keyed on
`(job_function_code, entity, department_type)` per the spec's role table.
Location keys come from the roster's region/abbreviation fields.

- [ ] **Step 1: Extend the roster CTE with location fields**

In the `roster` CTE, add these columns to the select:

```sql
            home_work_location_region,
            home_work_location_abbreviation,
```

- [ ] **Step 2: Add a role_access CTE before the final select**

Insert this CTE after `derived` (and before the final `select`), wiring from
`derived`. It encodes the 22-row role table. `summary_reporting_chain` is the
staff value for all non-leadership roles; leadership (CHIEF/EDHOS/SL/DSO) get
`detail`.

```sql
    role_access as (
        select
            d.*,

            -- scope_level per role × entity × department_type
            case
                when d.job_function_code = 'CHIEF' then 'network'
                when d.job_function_code = 'EDHOS' then 'region'
                when d.job_function_code in ('SL', 'DSO') then 'school'
                when d.job_function_code in ('ASL', 'DEAN', 'SCOPS',
                    'NINST', 'TEACH', 'TIR') then 'school'
                when d.job_function_code = 'MGDIR' and d.entity = 'KTAF'
                    then 'network'
                when d.job_function_code = 'MGDIR' and d.entity = 'Region'
                    then 'region'
                when d.job_function_code in ('DIR', 'KTRGS')
                    and d.entity = 'KTAF' then 'network + department_group'
                when d.job_function_code in ('DIR', 'KTRGS')
                    and d.entity = 'Region' then 'region + department_group'
                else 'none'
            end as scope_level,

            -- student_access_level: detail for instructional & leadership;
            -- summary for non-instructional network/regional staff
            case
                when d.job_function_code in ('CHIEF', 'EDHOS', 'SL', 'DSO',
                    'ASL', 'DEAN', 'SCOPS', 'NINST', 'TEACH', 'TIR')
                    then 'detail'
                when d.job_function_code in ('MGDIR', 'DIR', 'KTRGS')
                    and d.department_type = 'instructional' then 'detail'
                when d.job_function_code in ('MGDIR', 'DIR', 'KTRGS')
                    and d.department_type = 'non-instructional' then 'summary'
                else 'none'
            end as student_access_level,

            case
                when d.job_function_code in ('CHIEF', 'EDHOS', 'SL', 'DSO',
                    'ASL') then 'detail'
                when d.job_function_code in ('DEAN', 'SCOPS', 'NINST', 'TEACH',
                    'TIR', 'MGDIR', 'DIR', 'KTRGS')
                    then 'summary_reporting_chain'
                else 'none'
            end as staff_access_level,

            case
                when d.job_function_code in ('CHIEF', 'EDHOS', 'SL', 'DSO',
                    'ASL') then 'all'
                when d.job_function_code in ('DEAN', 'SCOPS', 'NINST', 'TEACH',
                    'TIR') then 'all'
                when d.job_function_code in ('MGDIR', 'DIR', 'KTRGS')
                    and d.department_type = 'instructional' then 'all'
                else 'none'
            end as student_pii_scope,

            case
                when d.job_function_code in ('CHIEF', 'EDHOS', 'SL', 'DSO')
                    then 'all'
                when d.job_function_code = 'ASL' then 'teaching_staff'
                else 'reporting_chain'
            end as staff_pii_scope,

            case
                when d.job_function_code in ('CHIEF', 'EDHOS', 'SL', 'DSO')
                    then 'all'
                when d.job_function_code = 'ASL' then 'teaching_staff'
                else 'reporting_chain'
            end as staff_compensation_scope,

            'none' as staff_benefits_scope,

            case
                when d.job_function_code in ('CHIEF', 'EDHOS', 'SL', 'DSO')
                    then 'all'
                when d.job_function_code = 'ASL' then 'teaching_staff'
                else 'reporting_chain'
            end as staff_observations_scope,

            case
                when d.job_function_code = 'CHIEF' then 'network'
                when d.job_function_code = 'EDHOS'
                    then d.home_work_location_region
                when d.job_function_code in ('SL', 'DSO', 'ASL', 'DEAN',
                    'SCOPS', 'NINST', 'TEACH', 'TIR')
                    then d.home_work_location_abbreviation
                when d.job_function_code = 'MGDIR' and d.entity = 'KTAF'
                    then 'network'
                when d.job_function_code = 'MGDIR' and d.entity = 'Region'
                    then d.home_work_location_region
                when d.job_function_code in ('DIR', 'KTRGS')
                    and d.entity = 'KTAF' then 'network'
                when d.job_function_code in ('DIR', 'KTRGS')
                    and d.entity = 'Region' then d.home_work_location_region
                else 'none'
            end as scope_key,
        from derived as d
    )
```

Note: `department_group` is the dept-group component of `scope_key` for the
compound scopes; `queryRewrite` reads `department_group` separately, so
`scope_key` here carries the location component (network sentinel / region / —).
For `network + department_group` and `region + department_group`, the dept-group
filter is applied via the `department_group` column, not `scope_key`.

- [ ] **Step 3: Update the final select to read from role_access**

Replace the final `select ... from derived` with:

```sql
select
    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as staff_key,

    google_email,
    job_function_code,
    job_function_level,
    entity,
    department_group,
    department_type,

    scope_level,
    scope_key,
    student_access_level,
    staff_access_level,
    student_pii_scope,
    staff_pii_scope,
    staff_compensation_scope,
    staff_benefits_scope,
    staff_observations_scope,
from role_access
```

- [ ] **Step 4: Build and verify against the spec's role table**

Run:

```bash
uv run dbt run --select dim_staff_cube_access \
  --project-dir src/dbt/kipptaf --target prod
uv run dbt show --inline \
  "select job_function_code, entity, department_type, scope_level, student_access_level, staff_access_level, staff_pii_scope from {{ ref('dim_staff_cube_access') }} qualify row_number() over (partition by job_function_code, entity, department_type order by staff_key) = 1 order by job_function_code" \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: one row per (code, entity, dept_type) combination; cross-check each
against the spec's role-based mapping table. (The `qualify` here is for spec
verification only — it is removed; the model itself has no qualify.)

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql
git commit -m "feat(dbt): add role-based scope and access CASEs to dim_staff_cube_access"
```

### Task 5: Access model — department special-access override + properties

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml`

The 8 special-access departments override the role-based row verbatim (network
scope, all/none scopes, `staff_access_level = detail`). Override wins entirely.

- [ ] **Step 1: Add a final resolution layer with the override**

Replace the final `select ... from role_access` with a CTE + select that applies
the override. Insert before the final select:

```sql
    resolved as (
        select
            ra.*,

            ra.assigned_department_name in (
                'Executive', 'Data', 'Human Resources',
                'Leadership Development', 'Teacher Development',
                'Accounting', 'Finance', 'Compliance'
            ) as is_special_access,
        from role_access as ra
    )
```

Then the final select applies the override per column. Replace the final select
with:

```sql
select
    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as staff_key,

    google_email,
    job_function_code,
    job_function_level,
    entity,
    department_group,
    department_type,

    if(is_special_access, 'network', scope_level) as scope_level,
    if(is_special_access, 'network', scope_key) as scope_key,

    case
        when not is_special_access then student_access_level
        when assigned_department_name in (
            'Human Resources', 'Leadership Development'
        ) then 'summary'
        else 'detail'
    end as student_access_level,

    if(is_special_access, 'detail', staff_access_level) as staff_access_level,

    case
        when not is_special_access then student_pii_scope
        when assigned_department_name in ('Executive', 'Data') then 'all'
        else 'none'
    end as student_pii_scope,

    if(is_special_access, 'all', staff_pii_scope) as staff_pii_scope,

    case
        when not is_special_access then staff_compensation_scope
        when assigned_department_name = 'Teacher Development' then 'none'
        else 'all'
    end as staff_compensation_scope,

    case
        when not is_special_access then staff_benefits_scope
        when assigned_department_name in (
            'Leadership Development', 'Teacher Development'
        ) then 'none'
        else 'all'
    end as staff_benefits_scope,

    case
        when not is_special_access then staff_observations_scope
        when assigned_department_name in (
            'Accounting', 'Finance', 'Compliance'
        ) then 'none'
        else 'all'
    end as staff_observations_scope,
from resolved
```

Note: `assigned_department_name` must be carried through `role_access` and
`resolved` — confirm it is in `derived.*` (it is, from Task 3 Step 1). The
special-access value mapping mirrors the spec's override table exactly.

- [ ] **Step 2: Build and verify the override**

Run:

```bash
uv run dbt run --select dim_staff_cube_access \
  --project-dir src/dbt/kipptaf --target prod
uv run dbt show --inline \
  "select department_group, scope_level, student_access_level, staff_compensation_scope, staff_observations_scope from {{ ref('dim_staff_cube_access') }} where department_group in ('Data','Teacher Development','Finance') qualify row_number() over (partition by department_group order by staff_key)=1" \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: Data → network/detail/all/all; Teacher Development →
network/detail/none(comp)/all(obs); Finance →
network/detail/all(comp)/none(obs). Cross-check the spec's override table.

- [ ] **Step 3: Write the properties YAML**

```yaml
models:
  - name: dim_staff_cube_access
    description: >-
      Cube access-control resolution: one row per active primary staff member,
      keyed on staff_key. Resolves scope (network/region/school, optionally
      narrowed by department_group), student/staff access levels, and per-field
      visibility scopes. A department special-access override (8 departments)
      wins over the role-based mapping keyed on (job_function_code, entity,
      department_type). Source of truth: the job groupings explorer and the
      mapping tables in
      docs/superpowers/specs/2026-06-03-cube-security-redesign.md. Reads
      int_people__staff_roster directly (documented exception to the
      no-ref-up-into-int marts rule). A person with no row here is
      default-denied by cube.js.
    columns:
      - name: staff_key
        data_type: string
        description: >-
          Primary key. Surrogate of employee_number, matching
          dim_staff.staff_key.
        constraints:
          - type: primary_key
            warn_unsupported: false
        data_tests:
          - unique
          - not_null
      - name: google_email
        data_type: string
        description: >-
          Resolve-only lookup for the JWT boundary in cube.js contextToGroups.
          Populated from the active primary roster row so a recycled address
          cannot resolve to a stale identity. Not the primary key.
        data_tests:
          - unique
      - name: job_function_code
        data_type: string
        description: Role code from the staff roster (CHIEF, EDHOS, SL, …).
      - name: job_function_level
        data_type: int64
        description: >-
          Org rank 1 (Chief, highest) to 6 (Teacher/Dean, lowest). Drives the
          staff-detail level gate. 99 indicates an unmapped job_function_code.
        data_tests:
          - accepted_values:
              arguments:
                values: [1, 2, 3, 4, 5, 6]
      - name: entity
        data_type: string
        description: KTAF or Region — distinguishes network vs regional roles.
      - name: department_group
        data_type: string
        description: >-
          Department rollup of assigned_department_name; narrows scope for
          department-scoped roles. Incomplete rollup pending data-team input
          (non-special departments currently 'other').
      - name: department_type
        data_type: string
        description:
          instructional or non-instructional — affects student access.
      - name: scope_level
        data_type: string
        description: >-
          Row-visibility scope: network, region, school, network +
          department_group, region + department_group, or none (deny). network
          is only ever set intentionally — unmatched resolves to none.
        data_tests:
          - accepted_values:
              arguments:
                values:
                  - network
                  - region
                  - school
                  - network + department_group
                  - region + department_group
                  - none
      - name: scope_key
        data_type: string
        description: >-
          Location component of scope: the sentinel 'network', a region value, a
          school abbreviation, or 'none'. Never NULL.
        data_tests:
          - not_null
      - name: student_access_level
        data_type: string
        description: detail / summary / none.
        data_tests:
          - accepted_values:
              arguments:
                values: [detail, summary, none]
      - name: staff_access_level
        data_type: string
        description: detail / summary_reporting_chain / none.
        data_tests:
          - accepted_values:
              arguments:
                values: [detail, summary_reporting_chain, none]
      - name: student_pii_scope
        data_type: string
        description: "all / none (future own_roster deferred)."
        data_tests:
          - accepted_values:
              arguments:
                values: [all, none]
      - name: staff_pii_scope
        data_type: string
        description: "all / reporting_chain / teaching_staff / none."
        data_tests:
          - accepted_values:
              arguments:
                values: [all, reporting_chain, teaching_staff, none]
      - name: staff_compensation_scope
        data_type: string
        description: "all / reporting_chain / teaching_staff / none."
        data_tests:
          - accepted_values:
              arguments:
                values: [all, reporting_chain, teaching_staff, none]
      - name: staff_benefits_scope
        data_type: string
        description:
          "all / reporting_chain / teaching_staff / none (all 'none'/'all' in
          v1)."
        data_tests:
          - accepted_values:
              arguments:
                values: [all, reporting_chain, teaching_staff, none]
      - name: staff_observations_scope
        data_type: string
        description: "all / reporting_chain / teaching_staff / none."
        data_tests:
          - accepted_values:
              arguments:
                values: [all, reporting_chain, teaching_staff, none]
```

- [ ] **Step 4: Parse, build, test**

Run:

```bash
uv run dbt build --select dim_staff_cube_access \
  --project-dir src/dbt/kipptaf --target prod
```

Expected: model builds and all tests (unique staff_key, accepted_values) PASS.

- [ ] **Step 5: trunk check**

Run:

```bash
.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml
```

Expected: no issues.

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml
git commit -m "feat(dbt): add department special-access override and properties to dim_staff_cube_access"
```

---

## Phase C — Cube schema test and renames

### Task 6: Cube schema-name CI test

**Files:**

- Create: `tests/cube/test_cube_schema.py`

Enforces that no cube `name:` uses a `dim_` / `fct_` prefix.

- [ ] **Step 1: Write the failing test**

```python
"""Schema conventions for Cube model YAML."""

from pathlib import Path

import yaml

CUBE_MODEL_DIR = Path(__file__).resolve().parents[2] / "src" / "cube" / "model"


def _cube_names() -> list[str]:
    names: list[str] = []
    for path in CUBE_MODEL_DIR.rglob("*.yml"):
        doc = yaml.safe_load(path.read_text())
        if not doc:
            continue
        for key in ("cubes", "views"):
            for entry in doc.get(key, []) or []:
                name = entry.get("name")
                if name:
                    names.append(name)
    return names


def test_no_dim_or_fct_prefix_on_cube_names() -> None:
    offenders = [
        n for n in _cube_names() if n.startswith("dim_") or n.startswith("fct_")
    ]
    assert not offenders, (
        f"Cube names must not use dim_/fct_ prefixes: {offenders}"
    )
```

- [ ] **Step 2: Run it — expect FAIL while old names exist**

Run:

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: FAIL listing any current `dim_`/`fct_` cube names (e.g.
`dim_student_enrollment_status`). This confirms the test detects offenders. If
there are currently none, it PASSES — that is acceptable; the test is a
going-forward guard.

- [ ] **Step 3: trunk check the test file**

```bash
.trunk/tools/trunk check --force tests/cube/test_cube_schema.py
```

Expected: no issues (ruff clean).

- [ ] **Step 4: Commit**

```bash
git add tests/cube/test_cube_schema.py
git commit -m "test(cube): enforce no dim_/fct_ prefix on cube names"
```

### Task 7: Rename existing cubes to drop dim*/fct* prefixes

**Files:**

- Modify (rename `name:` and `sql_table` references): every file under
  `src/cube/model/cubes/` and `src/cube/model/views/` whose cube `name:` starts
  with `dim_` or `fct_`, plus every YAML that references those names in a
  `join_path` or member prefix.

Per the issue's rename table. Current offenders on this branch:
`dim_student_enrollment_status` → `student_enrollment_status`,
`dim_student_enrollments` → `student_enrollments` (verify the live set first).

- [ ] **Step 1: List offenders and their references**

Run:

```bash
grep -rnE "name: (dim_|fct_)" src/cube/model/
grep -rnE "(dim_|fct_)[a-z_]+" src/cube/model/ | grep -E "join_path|prefix|sql_table|\{"
```

Expected: a list of cube definitions and the join/member references to rename.
Record the exact old→new pairs from the issue's rename table.

- [ ] **Step 2: Rename each cube definition and its file**

For each offender, change the `name:` field and rename the file to match
(`one cube per file, filename matches name:`). Update `sql_table` only if it
embeds the old name (it points at `kipptaf_marts.<table>`, which is unchanged —
do NOT rename the underlying dbt table). Use the rename table in the issue.

```bash
git mv src/cube/model/cubes/students/dim_student_enrollment_status.yml \
  src/cube/model/cubes/students/student_enrollment_status.yml
# then edit name: dim_student_enrollment_status -> name: student_enrollment_status
```

- [ ] **Step 3: Update all join_path / member-prefix references**

Across `src/cube/model/`, replace every `join_path:` segment and folder
member-prefix that used the old name. Per `src/cube/CLAUDE.md`, folder member
names derive from the last `join_path` segment, so a rename ripples into
`meta.folders[].members`. Grep again to confirm zero stragglers:

```bash
grep -rnE "dim_student_enrollment_status|dim_student_enrollments" src/cube/model/
```

Expected: no matches.

- [ ] **Step 4: Run the schema test — expect PASS**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: PASS (no `dim_`/`fct_` names remain).

- [ ] **Step 5: Commit**

```bash
git add -A src/cube/model/
git commit -m "refactor(cube): drop dim_/fct_ prefixes from cube names"
```

---

## Phase D — Staff cubes and views

> **Gate:** `dim_staff` and the new access marts must exist in `kipptaf_marts`
> (Phase B merged + materialized) for the cube to compile against prod. Until
> then, test via the dev-schema `sql_table` repoint pattern (Prerequisites).

### Task 8: Staff cube

**Files:**

- Create: `src/cube/model/cubes/staff/staff.yml`

Thin cube over `kipptaf_marts.dim_staff`, exposing `staff_key` (for the
reporting-chain filter), `job_function_code` and `job_function_level` (for the
level/teaching_staff filters), identity columns, and the FK to location for
scope. `public: false`.

- [ ] **Step 1: Write the cube YAML**

```yaml
cubes:
  - name: staff
    sql_table: kipptaf_marts.dim_staff
    public: false

    dimensions:
      - name: staff_key
        sql: staff_key
        type: string
        primary_key: true
        public: true

      - name: full_name
        sql: full_name
        type: string
        public: true

      - name: google_email
        sql: google_email
        type: string
        public: true

      - name: job_function_code
        sql: job_function_code
        type: string
        public: true

      - name: job_function_level
        sql: job_function_level
        type: number
        public: true
```

Note: `job_function_code` / `job_function_level` must be present on `dim_staff`.
If they are not (they live on the roster, not `dim_staff` today), add them to
`dim_staff` in a precursor dbt change, OR point this cube at a thin
`dim_staff` + access join. **Confirm during execution** which model carries
these columns at mart grain; adjust `sql_table`/`sql` accordingly. (Open item —
see Self-review note.)

- [ ] **Step 2: Validate compile via dev mode or /sql**

Per `src/cube/CLAUDE.md`, compile a trivial query through `/sql` (works against
`public: false`) to confirm the cube parses. Locally:

```bash
cd src/cube && npm run dev
```

Expected: server starts, no schema-compile error for `staff`.

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/cubes/staff/staff.yml
git commit -m "feat(cube): add staff cube over dim_staff"
```

### Task 9: Staff detail and summary views

**Files:**

- Create: `src/cube/model/views/staff/staff_detail.yml`
- Create: `src/cube/model/views/staff/staff_summary.yml`

Follow the attendance detail/summary pattern: `staff_detail` exposes row-level
identifiers + sensitive columns with two `access_policy` tiers
(`cube-access-staff-detail` excludes PII; `cube-access-staff-pii` includes all);
`staff_summary` omits identifiers and sensitive columns, single tier.

- [ ] **Step 1: Write staff_detail view**

```yaml
views:
  - name: staff_detail
    description: >-
      Row-level staff. One row per staff member. Contains direct identifiers and
      sensitive HR columns — see access_policy. Reporting-chain and field-scope
      row filtering is applied in cube.js queryRewrite.
    cubes:
      - join_path: staff
        includes:
          - staff_key
          - full_name
          - google_email
          - job_function_code
          - job_function_level

    access_policy:
      - group: cube-access-staff-detail
        member_level:
          includes: "*"
          excludes:
            - full_name
            - google_email
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
```

- [ ] **Step 2: Write staff_summary view**

```yaml
views:
  - name: staff_summary
    description: >-
      Aggregate staff counts and breakdowns. No direct identifiers. Single
      access tier — summary-scoped staff with no PII exposure.
    cubes:
      - join_path: staff
        includes:
          - job_function_code
          - job_function_level

    access_policy:
      # No PII tier — view contains no direct identifiers.
      - group: cube-access-staff-summary
        member_level:
          includes: "*"
      - group: cube-access-staff-detail
        member_level:
          includes: "*"
      - group: cube-access-staff-pii
        member_level:
          includes: "*"
```

[ ] **Step 3: Run cube schema test (no `dim*/fct*` names)**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: PASS.

- [ ] **Step 4: trunk check**

```bash
.trunk/tools/trunk check --force \
  src/cube/model/cubes/staff/staff.yml \
  src/cube/model/views/staff/staff_detail.yml \
  src/cube/model/views/staff/staff_summary.yml
```

Expected: no issues.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/cubes/staff/ src/cube/model/views/staff/
git commit -m "feat(cube): add staff_detail and staff_summary views"
```

### Task 9b: Migrate student view access_policy to the new group tiers

**Files:**

- Modify: `src/cube/model/views/attendance/attendance_detail.yml`
- Modify: `src/cube/model/views/attendance/attendance_summary.yml`
- Modify: `src/cube/model/views/students/student_enrollments_detail.yml`
- Modify: `src/cube/model/views/students/student_enrollments_summary.yml`

The existing student views gate on the old `cube-access-student-data` group, but
`buildGroups` (Task 10) emits `cube-access-student-detail` / `-summary` /
`-pii`. Migrate every student view to the new tiers, or no student access will
resolve.

- [ ] **Step 1: Update detail views**

In each `*_detail` view's `access_policy`, replace the single
`cube-access-student-data` block (which had the PII `excludes:`) with two
non-PII tiers that both carry the same `excludes:`, plus the unchanged
`cube-access-student-pii` tier. For `attendance_detail`:

```yaml
access_policy:
  - group: cube-access-student-detail
    member_level:
      includes: "*"
      excludes:
        - dim_students_full_name
        - dim_students_birth_date
        - dim_students_lea_student_identifier
        - dim_students_state_student_identifier
        - dim_students_salesforce_contact_id
        - dim_students_district_student_identifier
  - group: cube-access-student-pii
    member_level:
      includes: "*"
```

Apply the same shape to `student_enrollments_detail.yml`, preserving its own
existing `excludes:` PII list (read the file first — do not copy attendance's
list). Detail views do NOT list `cube-access-student-summary` (summary-only
users must not query detail views).

- [ ] **Step 2: Update summary views**

In each `*_summary` view, replace the single `cube-access-student-data` block
with all three tiers (summary users and above can read summary views):

```yaml
access_policy:
  # No PII tier — view contains no direct student identifiers.
  - group: cube-access-student-summary
    member_level:
      includes: "*"
  - group: cube-access-student-detail
    member_level:
      includes: "*"
  - group: cube-access-student-pii
    member_level:
      includes: "*"
```

Apply to both `attendance_summary.yml` and `student_enrollments_summary.yml`.

- [ ] **Step 3: Confirm no stale group name remains**

```bash
grep -rn "cube-access-student-data" src/cube/model/
```

Expected: no matches.

- [ ] **Step 4: trunk check the changed views**

```bash
.trunk/tools/trunk check --force \
  src/cube/model/views/attendance/attendance_detail.yml \
  src/cube/model/views/attendance/attendance_summary.yml \
  src/cube/model/views/students/student_enrollments_detail.yml \
  src/cube/model/views/students/student_enrollments_summary.yml
```

Expected: no issues.

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/views/
git commit -m "feat(cube): migrate student views to detail/summary/pii group tiers"
```

---

## Phase E — `cube.js` rewrite

> **Gate:** both access marts live in `kipptaf_marts`. Test on Cube Cloud Dev
> Mode (only Dev Mode surfaces `console.log`).

### Task 10: Replace contextToGroups with BigQuery resolution

**Files:**

- Modify: `src/cube/cube.js` — `contextToGroups` function (lines ~75-139) and
  the cache shape.

- [ ] **Step 1: Replace the contextToGroups body**

Replace the entire `contextToGroups: async ({ securityContext }) => { ... }`
block with the spec's version. Keep the `CUBE_GROUP_MAP` local-dev bypass and
`nextMidnightEastern()`. The new body:

```javascript
  contextToGroups: async ({ securityContext }) => {
    const email =
      securityContext?.email ??
      securityContext?.cubeCloud?.userAttributes?.email;
    if (!email) return [];

    if (process.env.NODE_ENV !== "production" && process.env.CUBE_GROUP_MAP) {
      try {
        const map = JSON.parse(process.env.CUBE_GROUP_MAP);
        const groups = (map[email] ?? []).filter((g) => g.startsWith("cube-"));
        groupCache.set(email, { groups, expiresAt: nextMidnightEastern() });
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

      const [accessRows] = await bq.query({
        query: `
          SELECT
            staff_key,
            student_access_level, staff_access_level,
            student_pii_scope, staff_pii_scope, staff_compensation_scope,
            staff_benefits_scope, staff_observations_scope,
            scope_level, scope_key, department_group, job_function_level
          FROM kipptaf_marts.dim_staff_cube_access
          WHERE google_email = @email
          LIMIT 1`,
        params: { email },
      });
      const row = accessRows[0] ?? null;

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

      const groups = buildGroups(row);
      groupCache.set(email, {
        groups,
        row,
        reporteeStaffKeys,
        expiresAt: nextMidnightEastern(),
      });
      return groups;
    } catch (err) {
      console.error(`contextToGroups failed for ${email}:`, err);
      return []; // default deny on failure
    }
  },
```

- [ ] **Step 2: Add the buildGroups helper**

Add above `module.exports` (near `nextMidnightEastern`):

```javascript
// Map a dim_staff_cube_access row to the cube-access-* group names that view
// access_policy blocks match on. Returns [] for a null row (default deny).
function buildGroups(row) {
  if (!row) return [];
  const groups = [];

  if (row.student_access_level === "detail") {
    groups.push("cube-access-student-detail");
  } else if (row.student_access_level === "summary") {
    groups.push("cube-access-student-summary");
  }
  if (row.student_pii_scope === "all") groups.push("cube-access-student-pii");

  if (row.staff_access_level === "detail") {
    groups.push("cube-access-staff-detail");
  } else if (row.staff_access_level === "summary_reporting_chain") {
    groups.push("cube-access-staff-summary");
    groups.push("cube-access-staff-detail");
  }
  if (row.staff_pii_scope !== "none") groups.push("cube-access-staff-pii");
  if (row.staff_compensation_scope !== "none") {
    groups.push("cube-access-staff-compensation");
  }
  if (row.staff_observations_scope !== "none") {
    groups.push("cube-access-staff-observations");
  }

  return groups;
}
```

Note: a `summary_reporting_chain` user gets BOTH `-summary` and `-detail` groups
because they see summary across scope AND detail on their chain; the row
restriction to the chain happens in `queryRewrite` (Task 12). Confirm this group
combination against the staff views' `access_policy` during validation (Task
14).

- [ ] **Step 3: Commit**

```bash
git add src/cube/cube.js
git commit -m "feat(cube): resolve contextToGroups from BigQuery access marts"
```

### Task 11: Replace location filter in queryRewrite

**Files:**

- Modify: `src/cube/cube.js` — `queryRewrite`, the location-scope block (lines
  ~160-203).

- [ ] **Step 1: Replace group-name location parsing with cache reads**

Replace the `networkGroup`/`regionGroup`/`schoolGroup` resolution and the
`locationFilter` if/else chain with reads from the cached `row`:

```javascript
const cached = email ? groupCache.get(email) : null;
const groups = cached?.expiresAt > Date.now() ? cached.groups : [];
const row = cached?.row ?? null;
const scopeLevel = row?.scope_level ?? "none";
const scopeKey = row?.scope_key ?? "none";

// ... student-cube member stripping stays (Task 12 updates its condition) ...

let locationFilter = null;
if (scopeLevel === "network" || scopeLevel === "network + department_group") {
  // no location filter (department_group narrowing handled separately)
} else if (
  scopeLevel === "region" ||
  scopeLevel === "region + department_group"
) {
  locationFilter = {
    member: "dim_locations.region_key",
    operator: "equals",
    values: [scopeKey],
  };
} else if (scopeLevel === "school") {
  locationFilter = {
    member: "dim_locations.abbreviation",
    operator: "equals",
    values: [scopeKey],
  };
} else {
  // scope_level 'none' or no row → default deny
  return {
    ...query,
    filters: [
      {
        member: "dim_locations.abbreviation",
        operator: "equals",
        values: [],
      },
    ],
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add src/cube/cube.js
git commit -m "feat(cube): read location scope from cache in queryRewrite"
```

### Task 12: Student-cube gating + staff reporting-chain filter

**Files:**

- Modify: `src/cube/cube.js` — student member-strip condition and the staff-cube
  block (lines ~308-320, the old `dim_staff.reporting_chain` segment).

- [ ] **Step 1: Update student member-strip condition**

Change the student strip to gate on the resolved access level rather than the
old `cube-access-student-data` group. Replace the
`if (!groups.includes("cube-access-student-data"))` guard with:

```javascript
const hasStudentAccess =
  row?.student_access_level === "detail" ||
  row?.student_access_level === "summary";
if (!hasStudentAccess) {
  query = {
    ...query,
    dimensions: (query.dimensions ?? []).filter((d) => !isStudentMember(d)),
    measures: (query.measures ?? []).filter((m) => !isStudentMember(m)),
  };
}
```

(`isStudentMember` is added in Task 13.)

- [ ] **Step 2: Replace the staff reporting-chain segment with row filters**

Replace the old `touchesStaffCube` / `dim_staff.reporting_chain` segment block
with reporting-chain + field-scope row filters:

```javascript
const touchesStaffCube = [
  ...(query.dimensions ?? []),
  ...(query.measures ?? []),
].some((m) => isStaffMember(m));

if (touchesStaffCube) {
  const level = row?.job_function_level ?? 99;
  const reportees = cached?.reporteeStaffKeys ?? [];

  // Detail visibility = downline ∩ strictly-below level.
  // Applied when the user's staff access is reporting-chain-scoped or a
  // reporting_chain / teaching_staff field is in play.
  const needsChainFilter =
    row?.staff_access_level === "summary_reporting_chain" &&
    row?.staff_pii_scope !== "all";

  if (needsChainFilter) {
    filters.push({
      member: "staff.staff_key",
      operator: "equals",
      values: reportees, // empty → IN () → deny
    });
    filters.push({
      member: "staff.job_function_level",
      operator: "gt",
      values: [String(level)],
    });
  }

  // teaching_staff field scope (ASL): restrict to TEACH/TIR rows.
  if (row?.staff_pii_scope === "teaching_staff") {
    filters.push({
      member: "staff.job_function_code",
      operator: "equals",
      values: ["TEACH", "TIR"],
    });
  }
}
```

Note: this is the v1 reduction of the spec's "group + row-filter pair." Validate
each scope value's behavior in Task 14; refine the `needsChainFilter` condition
if the data team's review (spec open question) changes the single-query
tradeoff.

- [ ] **Step 3: Commit**

```bash
git add src/cube/cube.js
git commit -m "feat(cube): gate student cubes and inject staff chain/level filters"
```

### Task 13: Replace STUDENT_CUBES/STAFF_CUBES arrays with prefix helpers

**Files:**

- Modify: `src/cube/cube.js` — remove `STUDENT_CUBES` / `STAFF_CUBES` arrays
  (lines ~23-35), add helpers.

- [ ] **Step 1: Add the prefix helpers, remove the arrays**

Delete the `STUDENT_CUBES` and `STAFF_CUBES` const arrays. Add near the top:

```javascript
// A query member is student-domain if its cube name starts with "student_",
// staff-domain if it starts with "staff_". Member format: "<cube>.<field>".
function isStudentMember(member) {
  return member.startsWith("student_");
}
function isStaffMember(member) {
  return member.startsWith("staff_");
}
```

Note: this requires student cubes to be named `student_*` and staff cubes
`staff_*`. The `attendance` cube is student-domain but not prefixed `student_` —
confirm whether `attendance` members must still be stripped for
no-student-access users. If so, keep an explicit allowance:

```javascript
function isStudentMember(member) {
  return member.startsWith("student_") || member.startsWith("attendance.");
}
```

Verify the live cube names during execution and adjust the prefix logic so every
student/staff cube is covered. (Open item — see Self-review.)

- [ ] **Step 2: Verify no remaining references to the removed arrays**

```bash
grep -nE "STUDENT_CUBES|STAFF_CUBES" src/cube/cube.js
```

Expected: no matches.

- [ ] **Step 3: Syntax-check cube.js**

```bash
node --check src/cube/cube.js
```

Expected: no output (valid syntax).

- [ ] **Step 4: trunk check**

```bash
.trunk/tools/trunk check --force src/cube/cube.js
```

Expected: no issues (prettier/eslint clean).

- [ ] **Step 5: Commit**

```bash
git add src/cube/cube.js
git commit -m "refactor(cube): replace cube arrays with isStudentMember/isStaffMember"
```

---

## Phase F — Validation and cutover

### Task 14: Dev Mode validation across tiers

**Files:** none (validation only).

- [ ] **Step 1: Open Cube Cloud Dev Mode on the branch**

Per `src/cube/CLAUDE.md`: Cube Cloud → Data Model → Dev Mode → add the branch.
Confirm `GOOGLE_DIRECTORY_SA_KEY` is no longer required, and that the Dev Mode
env has BigQuery credentials for the access-mart queries.

- [ ] **Step 2: Validate each tier with a test JWT**

For each persona, mint a JWT with that `email` claim (see `src/cube/CLAUDE.md`
MCP auth) and run a staff + student query. Expected outcomes:

| Persona (scope)       | staff_detail rows | student access          | comp visible   |
| --------------------- | ----------------- | ----------------------- | -------------- |
| CHIEF (network)       | all staff         | all students, detail    | all            |
| EDHOS (region)        | region staff      | region students         | all (region)   |
| SL (school)           | school staff      | school students         | all (school)   |
| TEACH (school, chain) | own downline only | school students summary | downline only  |
| ASL (school)          | school staff      | school students         | TEACH/TIR only |
| Data dept (special)   | all staff         | all students detail     | all            |
| unmatched email       | none (deny)       | none                    | none           |

Record actual vs expected. A `WHERE (1=0)` / `rlsAccessDenied` in `/sql` output
indicates default-deny fired (expected for the unmatched persona).

- [ ] **Step 3: Confirm reporting-chain correctness**

For the TEACH persona (a manager with reports), confirm `staff_detail` returns
exactly their downline (cross-check against
`dim_staff_reporting_chain WHERE manager_staff_key = <their key>`), and that a
peer at equal/higher level is absent.

- [ ] **Step 4: Document results in the PR**

Summarize the persona matrix (deidentified — no staff names/emails; use "Persona
A", row counts only) in the PR description.

### Task 15: Merge, materialize, retire Google groups

**Files:** none (operational).

- [ ] **Step 1: Open the PR**

Use `.github/pull_request_template.md`. Body references `Closes #4102`. Include
the deidentified persona-validation matrix.

- [ ] **Step 2: Confirm dbt Cloud CI green + warnings**

After CI passes, fetch warnings:
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`. Triage per
`marts/CLAUDE.md` pre-merge checklist.

- [ ] **Step 3: Squash-merge; confirm Cube Cloud prod redeploys**

Cube Cloud redeploys on merge to `main` (no manual deploy). Confirm the staff
cubes/views and new `cube.js` are live.

- [ ] **Step 4: Production spot-check**

Repeat Task 14's persona checks against production for at least one full school
day before group retirement.

- [ ] **Step 5: Retire cube-\* Google Workspace groups**

Once validated, hand off to IT to retire all `cube-*` Google Workspace groups —
access is fully managed by `dim_staff_cube_access`. (Operational; not a code
change. File a tracking issue if IT action is async.)

---

## Self-review notes (resolve during execution)

These are known open items the executing engineer must close, flagged rather
than hidden:

1. **`job_function_code` / `job_function_level` location for the cube.** The
   `staff` cube (Task 8) and the chain/level `queryRewrite` filters (Task 12)
   reference `staff.job_function_code` / `staff.job_function_level`. These come
   from the roster, not `dim_staff` today. Before Phase D, confirm whether
   `dim_staff` carries them (add via additive dbt change if not) or whether the
   staff cube must join `dim_staff_cube_access`. Resolve before Task 8 Step 1.

2. **Student-cube prefix coverage (Task 13).** `attendance` is student-domain
   but not `student_`-prefixed. Confirm the full set of student/staff cube names
   and make `isStudentMember` cover all of them (explicit allowance shown). The
   issue's rename of `attendance` → `student_attendance` may resolve this —
   apply that rename (Phase C) so the prefix helper is sufficient, and update
   the attendance view/cube references accordingly.

3. **`summary_reporting_chain` group combination (Task 10).** The buildGroups
   helper emits both `-summary` and `-detail` for these users; the chain row
   filter (Task 12) restricts detail rows. Validate (Task 14) that this does not
   leak detail columns for non-downline rows — if Cube's column grant ignores
   the row filter, fall back to two separate queries / views per the spec's
   discussion and re-confirm with the data team.

4. **dbt Cloud CI `job_function_code` dependency.** CI builds `state:modified+`;
   the access marts will fail CI until the roster change with
   `job_function_code` is merged. Sequence the roster PR first (or include the
   roster change), per `src/dbt/kipptaf/CLAUDE.md` cross-model coupling
   guidance.
