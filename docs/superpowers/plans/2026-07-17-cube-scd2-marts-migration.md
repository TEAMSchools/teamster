# Cube SCD2-to-dbt-Marts Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the two SCD2 period-intersection transforms currently living in
Cube-body `sql:` (`staff_reporting_relationships`, `staff_work_history`) into
dbt marts, rebase `dim_staff_reporting_chain` onto the new
`dim_staff_reporting_periods`, slim both cubes to `sql_table:`, and retire the
"SCD2 exception" from the one-model rule.

**Architecture:** Two new view marts materialize the period intersections:
`dim_staff_reporting_periods` (primary-assignment reporting windows) and
`dim_staff_work_history` (six-child SCD2 intersection, with the manager subquery
replaced by a `ref()` to the first mart). `dim_staff_reporting_chain` re-derives
its current-slice edges from `dim_staff_reporting_periods` so the reporting-edge
logic exists exactly once. The two cubes keep their names, join graphs,
dimensions, and measures; only their body changes from inline `sql:` to
`sql_table: kipptaf_marts.<new_mart>`.

**Tech Stack:** dbt (BigQuery, kipptaf project, contract-enforced view marts),
Cube semantic layer (YAML), `dbt_utils` (`generate_surrogate_key`,
`unique_combination_of_columns`, `expression_is_true`).

## Global Constraints

- Run all dbt via `uv run dbt ...` — never bare `dbt`. Project dir is
  `src/dbt/kipptaf`.
- New marts inherit `contract: enforced: true` and `materialized: view` from
  `dbt_project.yml` — **do not restate** them in properties YAML. No recursion
  in either new mart, so contract stays enforced (unlike
  `dim_staff_reporting_chain`, which disables it).
- Every mart column needs an exact `data_type` in properties (contract). Types
  confirmed from `kipptaf_marts.INFORMATION_SCHEMA.COLUMNS`: all `*_key`,
  `*_name`, `job_code`, `position_title`, `worker_type`, `department_name`,
  `business_unit_name` are `string`; `full_time_equivalency` is `float64`;
  `is_*` are `boolean`; `effective_*_date` are `date`.
- Surrogate PK = `<entity>_key` via `generate_surrogate_key([...])`; test with
  `unique` + `not_null` on the PK. Per `marts/CLAUDE.md`, do **not** add a
  separate `dbt_utils.unique_combination_of_columns` whose column set equals the
  hash inputs — `unique` on the PK detects the same violations.
- Every constraint block sets `warn_unsupported: false` (views).
- FK constraints use the column-level `to: ref(...)` + `to_columns:` form, plus
  a `relationships` data test for orphan detection.
- Source-agnostic column naming (marts R1–R10). Keep the column names verbatim
  from the current cube SQL (`effective_start_date`, `effective_end_date`,
  `work_location_key`, `status_reason`, `worker_type`) so the thin cubes' member
  references need no rewrite.
- No `zz_` dev-schema references in committed cube YAML
  (`grep -r "zz_" src/cube/` before any commit).
- Trunk formats at commit (`fmt`) and blocks at push (`check`). Do not run
  `trunk fmt`/`check` manually except the explicit `trunk check --force` step
  from inside the repo before pushing.
- Commits use conventional-commit messages. Frequent commits, one per task.

---

### Task 1: `dim_staff_reporting_periods` mart

The `staff_reporting_relationships` cube-body SQL, verbatim, converted to
`ref()`s. Grain: one row per `(staff_key, intersected effective_start_date)` →
`manager_staff_key`.

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_periods.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_periods.yml`

**Interfaces:**

- Consumes: `dim_work_assignment_primary`, `dim_staff_work_assignments`,
  `dim_work_assignment_reporting_relationships` (all existing marts).
- Produces: columns `staff_reporting_periods_key` (string PK), `staff_key`
  (string), `manager_staff_key` (string, nullable), `effective_start_date`
  (date), `effective_end_date` (date). Consumed by Task 2
  (`dim_staff_work_history` mgr join) and Task 3 (`dim_staff_reporting_chain`
  edges).

- [ ] **Step 1: Write the model SQL**

Create `dim_staff_reporting_periods.sql`:

```sql
{#-
  Point-in-time manager resolver. One row per staff member x contiguous window
  during which they held a single primary-assignment reporting relationship,
  formed by intersecting the primary work-assignment window with the reporting
  relationship window (greatest-start / least-end). The inclusive-overlap join
  guarantees start <= end for every emitted row. Consumed by
  dim_staff_work_history (point-in-time manager per period) and
  dim_staff_reporting_chain (current-slice reporting edges). Previously lived in
  the staff_reporting_relationships cube-body sql.
-#}
with
    reporting_periods as (
        select
            swa.staff_key,
            rr.manager_staff_key,
            greatest(
                wap.effective_start_date, rr.effective_start_date
            ) as effective_start_date,
            least(
                wap.effective_end_date, rr.effective_end_date
            ) as effective_end_date,
        from {{ ref("dim_work_assignment_primary") }} as wap
        inner join
            {{ ref("dim_staff_work_assignments") }} as swa
            on wap.work_assignment_key = swa.work_assignment_key
            and swa.staff_key is not null
        inner join
            {{ ref("dim_work_assignment_reporting_relationships") }} as rr
            on rr.work_assignment_key = wap.work_assignment_key
            and wap.effective_start_date <= rr.effective_end_date
            and wap.effective_end_date >= rr.effective_start_date
        where wap.is_primary_position
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["staff_key", "effective_start_date"]
        )
    }} as staff_reporting_periods_key,
    staff_key,
    manager_staff_key,
    effective_start_date,
    effective_end_date,
from reporting_periods
```

- [ ] **Step 2: Write the properties YAML**

Create `properties/dim_staff_reporting_periods.yml`:

```yaml
models:
  - name: dim_staff_reporting_periods
    description: >-
      Point-in-time manager resolver. One row per staff member per contiguous
      window during which they held a single primary work-assignment reporting
      relationship, formed by intersecting the primary work-assignment validity
      window with the reporting-relationship window. Consumed by the Cube
      semantic layer (staff_reporting_relationships helper cube) and by
      dim_staff_work_history / dim_staff_reporting_chain.
    data_tests:
      - dbt_utils.expression_is_true:
          arguments:
            expression: effective_start_date <= effective_end_date
    columns:
      - name: staff_reporting_periods_key
        data_type: string
        description: Surrogate primary key of (staff_key, effective_start_date).
        constraints:
          - type: primary_key
            warn_unsupported: false
        data_tests:
          - unique
          - not_null
      - name: staff_key
        data_type: string
        description: Foreign key to `dim_staff.staff_key` — the reportee.
        constraints:
          - type: foreign_key
            to: ref('dim_staff')
            to_columns: [staff_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_staff')
                field: staff_key
      - name: manager_staff_key
        data_type: string
        description: >-
          Foreign key to `dim_staff.staff_key` — the manager for this period.
          Nullable: a primary reporting-relationship row may carry no manager.
        constraints:
          - type: foreign_key
            to: ref('dim_staff')
            to_columns: [staff_key]
            warn_unsupported: false
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_staff')
                field: staff_key
      - name: effective_start_date
        data_type: date
        description: Start of the contiguous reporting-relationship period.
        data_tests:
          - not_null
      - name: effective_end_date
        data_type: date
        description:
          End (inclusive) of the contiguous reporting-relationship period.
        data_tests:
          - not_null
```

- [ ] **Step 3: Build and test the model**

Run (from repo root):

```bash
uv run dbt build \
  --select dim_staff_reporting_periods \
  --defer --favor-state --state src/dbt/kipptaf/target/prod \
  --project-dir src/dbt/kipptaf --target dev
```

Expected: model builds into
`zz_<username>_kipptaf_marts.dim_staff_reporting_periods`; `unique`, `not_null`,
`relationships`, and `expression_is_true` tests PASS.

> If `target/prod` state is absent, generate it first
> (`uv run dbt compile --project-dir src/dbt/kipptaf --target prod` or download
> the prod manifest per repo tooling), or omit `--defer/--state` and add
> upstream dims to `--select` with a leading `+`.

- [ ] **Step 4: CHECKPOINT — verify PK uniqueness**

If `unique` on `staff_reporting_periods_key` FAILS, a staff member has two
concurrent reporting relationships whose intersected windows share a start date
(the documented ADP dual-reporting data-quality issue — see the dedup TODO in
`dim_staff_reporting_chain.sql`). **Do not add a defensive dedupe.** Query the
colliding rows, then STOP and surface to the user with the specific
`(staff_key, effective_start_date, manager_staff_key)` collisions before
deciding between (a) downgrading the PK `unique` test to `severity: warn` with a
`TODO(#<dual-reporting-issue>)`, or (b) a product decision on which manager
wins. The live PR validation (8/8 matrix) suggests current data is clean, so
this is a guard, not an expectation.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_periods.sql \
        src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_periods.yml
git commit -m "feat(dbt): add dim_staff_reporting_periods mart"
```

---

### Task 2: `dim_staff_work_history` mart

The `staff_work_history` cube-body SQL, converted to `ref()`s, with the inline
`mgr` subquery replaced by a `ref()` to `dim_staff_reporting_periods` and an
explicit `where` dropping non-overlapping (start-after-end) combinations.

**Files:**

- Create: `src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_history.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_history.yml`

**Interfaces:**

- Consumes: `dim_staff_work_assignments`, `dim_work_assignment_status`,
  `dim_work_assignment_jobs`, `dim_work_assignment_types`,
  `dim_work_assignment_organizational_units`, `dim_work_assignment_locations`,
  `dim_work_assignment_primary`, and `dim_staff_reporting_periods` (Task 1).
- Produces: columns `staff_work_history_key` (string PK), `work_assignment_key`
  (string), `staff_key` (string), `full_time_equivalency` (float64),
  `is_management_position` (boolean), `status_name` (string), `status_reason`
  (string), `position_title` (string), `job_code` (string), `worker_type`
  (string), `department_name` (string), `business_unit_name` (string),
  `work_location_key` (string, nullable), `is_primary_position` (boolean),
  `manager_staff_key` (string, nullable), `effective_start_date` (date),
  `effective_end_date` (date). Consumed by the thin `staff_work_history` cube
  (Task 4).

- [ ] **Step 1: Write the model SQL**

Create `dim_staff_work_history.sql`:

```sql
{#-
  SCD2 period intersection: one row per work assignment x contiguous window
  during which the worker's status, job, worker type, home org unit, location,
  AND point-in-time manager all held simultaneously. Overlaps are anchored to
  the assignment-level status period (dim_work_assignment_status); greatest /
  least then collapse each combination to its true effective range. Manager is
  folded in via dim_staff_reporting_periods (left join + coalesce keeps
  manager-less staff). Combinations whose children do not mutually overlap yield
  start > end and are dropped by the final where. Previously lived in the
  staff_work_history cube-body sql (with the manager logic copy-pasted inline).
-#}
with
    work_history as (
        select
            swa.work_assignment_key,
            swa.staff_key,
            swa.full_time_equivalency,
            swa.is_management_position,
            was.status_name,
            was.reason_name as status_reason,
            wj.position_title,
            wj.job_code,
            wt.worker_type_name as worker_type,
            wo.department_name,
            wo.business_unit_name,
            wl.location_key as work_location_key,
            wp.is_primary_position,
            mgr.manager_staff_key,
            greatest(
                was.effective_start_date,
                wj.effective_start_date,
                wt.effective_start_date,
                wo.effective_start_date,
                wl.effective_start_date,
                coalesce(mgr.effective_start_date, date '1900-01-01')
            ) as effective_start_date,
            least(
                was.effective_end_date,
                wj.effective_end_date,
                wt.effective_end_date,
                wo.effective_end_date,
                wl.effective_end_date,
                coalesce(mgr.effective_end_date, date '9999-12-31')
            ) as effective_end_date,
        from {{ ref("dim_staff_work_assignments") }} as swa
        inner join
            {{ ref("dim_work_assignment_status") }} as was
            on was.work_assignment_key = swa.work_assignment_key
        inner join
            {{ ref("dim_work_assignment_jobs") }} as wj
            on wj.work_assignment_key = swa.work_assignment_key
            and was.effective_start_date < wj.effective_end_date
            and was.effective_end_date > wj.effective_start_date
        inner join
            {{ ref("dim_work_assignment_types") }} as wt
            on wt.work_assignment_key = swa.work_assignment_key
            and was.effective_start_date < wt.effective_end_date
            and was.effective_end_date > wt.effective_start_date
        inner join
            {{ ref("dim_work_assignment_organizational_units") }} as wo
            on wo.work_assignment_key = swa.work_assignment_key
            and wo.assignment_type = 'home'
            and was.effective_start_date < wo.effective_end_date
            and was.effective_end_date > wo.effective_start_date
        inner join
            {{ ref("dim_work_assignment_locations") }} as wl
            on wl.work_assignment_key = swa.work_assignment_key
            and was.effective_start_date < wl.effective_end_date
            and was.effective_end_date > wl.effective_start_date
        left join
            {{ ref("dim_work_assignment_primary") }} as wp
            on wp.work_assignment_key = swa.work_assignment_key
            and was.effective_start_date < wp.effective_end_date
            and was.effective_end_date > wp.effective_start_date
        left join
            {{ ref("dim_staff_reporting_periods") }} as mgr
            on mgr.staff_key = swa.staff_key
            and was.effective_start_date < mgr.effective_end_date
            and was.effective_end_date > mgr.effective_start_date
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["work_assignment_key", "effective_start_date"]
        )
    }} as staff_work_history_key,
    work_assignment_key,
    staff_key,
    full_time_equivalency,
    is_management_position,
    status_name,
    status_reason,
    position_title,
    job_code,
    worker_type,
    department_name,
    business_unit_name,
    work_location_key,
    is_primary_position,
    manager_staff_key,
    effective_start_date,
    effective_end_date,
from work_history
where effective_start_date <= effective_end_date
```

- [ ] **Step 2: Write the properties YAML**

Create `properties/dim_staff_work_history.yml`:

```yaml
models:
  - name: dim_staff_work_history
    description: >-
      SCD2 period-intersection dimension. One row per work assignment per
      contiguous window during which the worker's status, job, worker type, home
      org unit, work location, and point-in-time manager all held
      simultaneously. Consumed by the Cube semantic layer (staff_work_history
      cube feeding the staff_directory and staff_pii views).
    data_tests:
      - dbt_utils.expression_is_true:
          arguments:
            expression: effective_start_date <= effective_end_date
    columns:
      - name: staff_work_history_key
        data_type: string
        description:
          Surrogate primary key of (work_assignment_key, effective_start_date).
        constraints:
          - type: primary_key
            warn_unsupported: false
        data_tests:
          - unique
          - not_null
      - name: work_assignment_key
        data_type: string
        description:
          Foreign key to `dim_staff_work_assignments.work_assignment_key`.
        constraints:
          - type: foreign_key
            to: ref('dim_staff_work_assignments')
            to_columns: [work_assignment_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_staff_work_assignments')
                field: work_assignment_key
      - name: staff_key
        data_type: string
        description: Foreign key to `dim_staff.staff_key`.
        constraints:
          - type: foreign_key
            to: ref('dim_staff')
            to_columns: [staff_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_staff')
                field: staff_key
      - name: manager_staff_key
        data_type: string
        description: >-
          Foreign key to `dim_staff.staff_key` — point-in-time manager for the
          period. Nullable for manager-less staff.
        constraints:
          - type: foreign_key
            to: ref('dim_staff')
            to_columns: [staff_key]
            warn_unsupported: false
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_staff')
                field: staff_key
      - name: work_location_key
        data_type: string
        description: >-
          Foreign key to `dim_locations.location_key`. Nullable when the ADP
          location has no canonical mapping.
        constraints:
          - type: foreign_key
            to: ref('dim_locations')
            to_columns: [location_key]
            warn_unsupported: false
        data_tests:
          - relationships:
              arguments:
                to: ref('dim_locations')
                field: location_key
      - name: status_name
        data_type: string
        description: >-
          Assignment-level employment status during this period (Active, Leave,
          Terminated), from dim_work_assignment_status.
      - name: status_reason
        data_type: string
        description: >-
          Reason for the status (leave type or termination reason). Null for
          many Active periods.
      - name: position_title
        data_type: string
        description:
          Free-text position title for the work assignment during this period.
      - name: job_code
        data_type: string
        description: Job code for the work assignment during this period.
      - name: worker_type
        data_type: string
        description: ADP worker type display name (e.g. Regular, Temporary).
      - name: department_name
        data_type: string
        description: Home Department display name during this period.
      - name: business_unit_name
        data_type: string
        description: Home Business Unit display name during this period.
      - name: is_primary_position
        data_type: boolean
        description: >-
          True if this was the worker's primary work assignment during the
          period.
      - name: is_management_position
        data_type: boolean
        description:
          True if this work assignment is designated a management position.
      - name: full_time_equivalency
        data_type: float64
        description: FTE ratio for the assignment (1.0 = full-time).
      - name: effective_start_date
        data_type: date
        description:
          Start of the contiguous period (intersection of all SCD2 children).
      - name: effective_end_date
        data_type: date
        description: End (inclusive) of the contiguous period.
```

- [ ] **Step 3: Build and test the model**

```bash
uv run dbt build \
  --select dim_staff_work_history \
  --defer --favor-state --state src/dbt/kipptaf/target/prod \
  --project-dir src/dbt/kipptaf --target dev
```

Expected: builds into `zz_<username>_kipptaf_marts.dim_staff_work_history`; all
tests PASS.

- [ ] **Step 4: CHECKPOINT — verify PK uniqueness and manager non-fan-out**

If `unique` on `staff_work_history_key` FAILS, the `mgr` left join fanned out —
`dim_staff_reporting_periods` returned two manager rows overlapping one status
period (same dual-reporting root cause as Task 1 Step 4). Do **not** add a
defensive dedupe. Query the collisions and STOP to surface to the user — the
resolution is tied to the Task 1 decision (fix the grain at the source mart, not
here).

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_history.sql \
        src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_history.yml
git commit -m "feat(dbt): add dim_staff_work_history mart"
```

---

### Task 3: Rebase `dim_staff_reporting_chain` onto `dim_staff_reporting_periods`

The current-slice reporting edges move from a hand-rolled join (primary +
assignments + reporting_relationships) to reading `dim_staff_reporting_periods`,
so the edge derivation exists exactly once. The recursive closure, `all_staff`,
self-pairs, and `contract: enforced: false` are unchanged.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql`

**Interfaces:**

- Consumes: `dim_staff_reporting_periods` (Task 1) — current-slice edges.
- Produces: unchanged output columns `manager_staff_key`, `reportee_staff_key`,
  `depth`.

- [ ] **Step 1: Replace the `raw_edges` CTE**

In `dim_staff_reporting_chain.sql`, replace the `raw_edges` CTE (which reads
`dim_staff_work_assignments` + `dim_work_assignment_primary` +
`dim_work_assignment_reporting_relationships`) with a read of the current slice
of `dim_staff_reporting_periods`. The `is_primary_position` and
`staff_key is not null` filters are already baked into the mart, so only the
current-window and non-null-manager filters remain:

```sql
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    raw_edges as (
        select
            staff_key as reportee_staff_key,
            manager_staff_key,
        from {{ ref("dim_staff_reporting_periods") }}
        where
            manager_staff_key is not null
            and current_date('{{ var("local_timezone") }}')
            between effective_start_date and effective_end_date
    ),
```

> Confirm the timezone var name used elsewhere in kipptaf marts (grep
> `current_date(` under `src/dbt/kipptaf/models/marts`). If marts use bare
> `current_date()`, match that instead of `var("local_timezone")`.

Keep the `edges` (dedupe), `closure`, `all_staff`, `combined`, and final
`select` CTEs exactly as they are. Update the model's leading `{#- ... -#}`
comment: the edges now come from `dim_staff_reporting_periods` (current slice),
not directly from the three work-assignment dims.

- [ ] **Step 2: Build and test**

```bash
uv run dbt build \
  --select dim_staff_reporting_chain \
  --defer --favor-state --state src/dbt/kipptaf/target/prod \
  --project-dir src/dbt/kipptaf --target dev
```

Expected: builds; `unique_combination_of_columns` + `not_null` + `relationships`
tests PASS.

- [ ] **Step 3: CHECKPOINT — row-count parity**

Compare the rebased closure to prod to confirm the edge source swap did not
change the org tree. Query both and diff counts:

```sql
select count(*) as n, count(distinct reportee_staff_key) as n_reportees
from `zz_<username>_kipptaf_marts`.dim_staff_reporting_chain;
-- vs prod:
select count(*) as n, count(distinct reportee_staff_key) as n_reportees
from `teamster-332318`.kipptaf_marts.dim_staff_reporting_chain;
```

Expected: counts within noise (a small delta is acceptable if ADP data shifted
between builds; a large delta means the current-slice filter is wrong — revisit
Step 1's window predicate). Surface any material delta to the user before
proceeding.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql
git commit -m "refactor(dbt): rebase dim_staff_reporting_chain onto dim_staff_reporting_periods"
```

---

### Task 4: Slim the two cubes to `sql_table:`

Both cubes keep their names, `public: false`, join graphs, dimensions, and
measures. Only the body changes from inline `sql:` to `sql_table:`, and the
primary-key dimensions stop being `CONCAT(...)` expressions (they now read the
mart's surrogate-key column).

**Files:**

- Modify: `src/cube/model/cubes/staff/staff_reporting_relationships.yml`
- Modify: `src/cube/model/cubes/staff/staff_work_history.yml`

**Interfaces:**

- Consumes: `kipptaf_marts.dim_staff_reporting_periods`,
  `kipptaf_marts.dim_staff_work_history` (Tasks 1–2).
- Produces: unchanged public cube surface (same dimension/measure names) — the
  `staff_directory` / `staff_pii` views need no edits.

- [ ] **Step 1: Rewrite `staff_reporting_relationships.yml`**

Replace the whole file with (body → `sql_table`; PK dim → mart column; drop the
stale `{CUBE}`-qualified rationale, which referenced a work_history join that no
longer exists):

```yaml
cubes:
  - name: staff_reporting_relationships
    public: false
    # Point-in-time manager resolver. One row per staff member x contiguous
    # window during which they held a single primary-assignment reporting
    # relationship. Helper cube only, not exposed in any view. Reads the
    # dim_staff_reporting_periods mart (the period intersection is materialized
    # there, not in cube sql — src/cube/CLAUDE.md "Transformation lives in
    # dbt"). Retained for future fact cubes (observations, gradebook, surveys)
    # that resolve manager point-in-time by joining on their own event date.
    sql_table: kipptaf_marts.dim_staff_reporting_periods

    dimensions:
      - name: staff_reporting_relationship_key
        description:
          Surrogate key (staff_key, intersected effective_start_date). Primary
          key.
        sql: staff_reporting_periods_key
        type: string
        primary_key: true

      - name: staff_key
        description: FK to staff — the reportee.
        sql: staff_key
        type: string
        public: true

      - name: manager_staff_key
        description: FK to staff (via staff_manager alias) — the manager.
        sql: manager_staff_key
        type: string
        public: true

      - name: effective_start_date
        description: Start of the contiguous reporting-relationship period.
        sql: "CAST({CUBE}.effective_start_date AS TIMESTAMP)"
        type: time
        public: true

      - name: effective_end_date
        description: End of the contiguous reporting-relationship period.
        sql: "CAST({CUBE}.effective_end_date AS TIMESTAMP)"
        type: time
        public: true
```

- [ ] **Step 2: Rewrite the body of `staff_work_history.yml`**

Change only the cube header comment, the `sql: |` block (→ `sql_table:`), and
the `staff_work_history_key` dimension (→ mart column). Leave the `joins:`,
remaining `dimensions:`, and `measures:` blocks byte-for-byte unchanged.

Header comment + body become:

```yaml
cubes:
  - name: staff_work_history
    public: false
    # SCD2 period intersection: one row per work assignment x contiguous window
    # during which the worker's status, job, worker type, home org unit,
    # location, AND point-in-time manager all held simultaneously. Reads the
    # dim_staff_work_history mart (the intersection is materialized there, not
    # in cube sql — src/cube/CLAUDE.md "Transformation lives in dbt"). The dates
    # BETWEEN range join below stays in cube (sanctioned join-sql use); each
    # period carries exactly one manager, so a single-day query returns one row
    # per person.
    sql_table: kipptaf_marts.dim_staff_work_history

    joins:
      # ... (unchanged)
```

And the PK dimension:

```yaml
- name: staff_work_history_key
  description: >-
    Surrogate key (work_assignment_key, intersected effective_start_date).
    Primary key.
  sql: staff_work_history_key
  type: string
  primary_key: true
```

- [ ] **Step 3: Verify no stale `sql:` blocks or `zz_` references remain**

```bash
grep -n "kipptaf_marts\." src/cube/model/cubes/staff/staff_reporting_relationships.yml \
                          src/cube/model/cubes/staff/staff_work_history.yml
grep -rn "zz_" src/cube/ || echo "no zz_ refs — good"
```

Expected: each file shows exactly one `sql_table: kipptaf_marts.<mart>` line and
no `SELECT`/`JOIN`; no `zz_` references anywhere under `src/cube/`.

- [ ] **Step 4: Confirm the views still reference only existing members**

```bash
grep -rn "staff_work_history\|staff_reporting_relationships" src/cube/model/views/
```

Expected: any member referenced by `staff_directory` / `staff_pii` from these
cubes (e.g. `status_name`, `department_name`, `count_employees`) still exists as
a dimension/measure in the rewritten cubes. No view edits should be needed;
confirm and note if any member was renamed (none should be).

- [ ] **Step 5: Commit**

```bash
git add src/cube/model/cubes/staff/staff_reporting_relationships.yml \
        src/cube/model/cubes/staff/staff_work_history.yml
git commit -m "refactor(cube): slim staff SCD2 cubes to sql_table over dbt marts"
```

---

### Task 5: Register marts in the Cube exposure + fix the `staff_cube_access` header

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/cube.yml`
- Modify: `src/cube/model/cubes/staff/staff_cube_access.yml`

- [ ] **Step 1: Add the two marts to the exposure `depends_on`**

In `cube.yml`, add `- ref("dim_staff_reporting_periods")` immediately after the
existing `- ref("dim_staff_reporting_chain")` line, and
`- ref("dim_staff_work_history")` immediately after
`- ref("dim_staff_work_assignments")`.

- [ ] **Step 2: Fix the stale `staff_cube_access.yml` header comment**

Replace the header comment (lines 4–13, the block from `# Exposes only` through
`# attributes need to be queryable dimensions.`) with one that names
`staff_work_history` and the extends-diamond rationale:

```yaml
# Exposes only the three access-control role attributes from
# dim_staff_cube_access (job_function_level/code, department_group) as
# queryable dimensions for the staff views' access_policy remit and display.
# Surfaced onto the staff views via a Cube join from staff_work_history on
# staff_key (see staff_work_history.yml) — attached there rather than on
# `staff` because the manager alias staff_manager extends `staff` and would
# inherit a staff-level join, creating an ambiguous second path to
# staff_cube_access in staff_directory (which joins both). The scope columns
# (staff_*_scope, region_key, location_abbreviation, ...) are NOT exposed
# here — resolveAccess reads those directly from dim_staff_cube_access to
# build the securityContext; only these three role attributes need to be
# queryable dimensions.
```

> Verify the join placement claim against `staff_work_history.yml`'s
> `staff_cube_access` join comment before finalizing wording — keep them
> consistent.

- [ ] **Step 3: Parse-check the exposure**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
```

Expected: parses with no error; the two new refs resolve.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/exposures/cube.yml \
        src/cube/model/cubes/staff/staff_cube_access.yml
git commit -m "chore: register SCD2 marts in cube exposure; fix staff_cube_access header"
```

---

### Task 6: Retire the SCD2 exception from `src/cube/CLAUDE.md`

**Files:**

- Modify: `src/cube/CLAUDE.md`

- [ ] **Step 1: Restore the belongs-in-dbt parenthetical**

In the "Transformation lives in dbt, not cube" bullet, change:

```text
Multi-table joins, window functions, and derived grains (status spines and
most SCD2 work) belong in a dbt mart.
```

to:

```text
Multi-table joins, window functions, and derived grains (SCD2
period-intersection / status spines) belong in a dbt mart.
```

- [ ] **Step 2: Delete the SCD2 exception block**

Remove the entire `**Exception — SCD2 period intersection** ...` passage —
everything from `**Exception — SCD2 period intersection**` through the closing
`... model that as a Cube join.` — so the bullet ends at
`... confirm the one-model rule.)`. The one-model rule now holds with zero
exceptions.

- [ ] **Step 3: Verify no other CLAUDE.md text still claims the exception**

```bash
grep -rn "SCD2 exception\|cube-body \`sql:\` MAY\|sanctioned multi-table join" src/cube/CLAUDE.md \
  || echo "no stale exception text — good"
```

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add src/cube/CLAUDE.md
git commit -m "docs(cube): drop SCD2 exception now that period intersection lives in dbt marts"
```

---

### Task 7: Full validation + Python schema test

**Files:**

- Test: `tests/cube/test_cube_schema.py` (run; modify only if it enumerates cube
  bodies / mart mappings that changed)

- [ ] **Step 1: Build the whole changed set together with tests**

```bash
uv run dbt build \
  --select dim_staff_reporting_periods dim_staff_work_history dim_staff_reporting_chain \
  --defer --favor-state --state src/dbt/kipptaf/target/prod \
  --project-dir src/dbt/kipptaf --target dev
```

Expected: 3 models build, all data tests PASS.

- [ ] **Step 2: Run the Cube Python schema test**

```bash
uv run pytest tests/cube/test_cube_schema.py -v
```

Expected: PASS. If it fails because it asserts something about the old inline
`sql:` bodies or a cube→mart mapping, update the test to match the thin cubes
(add the two new marts / drop the inline-sql assertion) and re-run.

- [ ] **Step 3: Run the Cube JS unit tests (guard against unrelated breakage)**

```bash
npm --prefix src/cube test
```

Expected: existing `access.test.js` / `cube.test.js` suites still PASS (this
change touches no JS; a failure means an unrelated regression).

- [ ] **Step 4: Trunk-check every changed file from inside the repo**

```bash
/workspaces/teamster/.trunk/tools/trunk check --no-fix --force </dev/null \
  src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_periods.sql \
  src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_history.sql \
  src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_periods.yml \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_history.yml \
  src/cube/model/cubes/staff/staff_reporting_relationships.yml \
  src/cube/model/cubes/staff/staff_work_history.yml \
  src/cube/model/cubes/staff/staff_cube_access.yml \
  src/dbt/kipptaf/models/exposures/cube.yml \
  src/cube/CLAUDE.md
```

Expected: no sqlfluff / yamllint / markdownlint findings. Fix any and re-run.

- [ ] **Step 5: Final grep for dev-schema leakage**

```bash
grep -rn "zz_" src/cube/ && echo "LEAK — revert before push" || echo "clean"
```

Expected: `clean`.

- [ ] **Step 6: Push and hand off to reviewer**

Push the branch (do not force). Post a PR comment mapping each of cbini's seven
requested changes to its commit, calling out any convention deviation (the PK
`unique` test standing in for `unique_combination_of_columns` per
`marts/CLAUDE.md`) and any CHECKPOINT findings. Ping cbini to re-verify live —
the branch-staging Cube env reads prod `kipptaf_marts`, so the two new marts
must be merged + materialized before the RLS matrix can be re-run there (note
this in the ping).

---

## Self-Review

**Spec coverage** — cbini's seven requested changes:

1. `dim_staff_reporting_periods` mart → Task 1. ✅
2. `dim_staff_work_history` mart (mgr via `ref`, explicit start≤end `where`) →
   Task 2. ✅
3. Rebase `dim_staff_reporting_chain` onto `dim_staff_reporting_periods` →
   Task 3. ✅
4. Properties + tests (contract enforced, `not_null` keys, grain uniqueness,
   `expression_is_true` start≤end, `relationships` to parents) → Tasks 1–2 YAML.
   Grain uniqueness is enforced via `unique` on the surrogate PK per
   `marts/CLAUDE.md` (documented deviation from the literal
   `unique_combination_of_columns` ask). Per-key mutual-non-overlap test noted
   by cbini as a fine-as-follow-up; not included (can be a separate custom
   test). ✅ (with noted deviation)
5. Cubes go thin (`sql:` → `sql_table:`, names + joins kept, dates BETWEEN
   stays) → Task 4. ✅
6. CLAUDE.md — drop SCD2 exception, restore belongs-in-dbt phrasing → Task 6. ✅
7. Register both marts in `exposures/cube.yml`; fix `staff_cube_access.yml`
   header → Task 5. ✅

**Deviations flagged for the reviewer:** (a) `unique` PK test instead of
`unique_combination_of_columns` (item 4); (b) per-key mutual-non-overlap test
deferred (cbini permitted). Both surfaced in the Task 7 Step 6 PR comment.

**Open risk:** dual-manager ADP data quality could break PK uniqueness on
`dim_staff_reporting_periods` (Task 1 Step 4 checkpoint) and cascade to
`dim_staff_work_history` (Task 2 Step 4). Handled as a STOP-and-surface
checkpoint, not a silent dedupe.
