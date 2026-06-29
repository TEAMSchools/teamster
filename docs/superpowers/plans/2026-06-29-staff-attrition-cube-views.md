# Staff Attrition Cube Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `fct_staff_attrition` and expose it via a
`staff_attrition_summary` Cube view with per-methodology attrition rates,
work-context breakdowns, and a weekly/monthly trend axis.

**Architecture:** The dbt fact stays at cohort grain (one row per employee ×
academic year × attrition type); new columns add `staff_key`, window bounds, and
`as_of_exit_date` to enable Cube joins. A `staff_attrition` cube joins the fact
to `staff_work_history` (point-in-time exit context) and to a new
`attrition_periods` cube (`extends: dates` — the trend spine, avoiding a diamond
with `staff_work_history.dates`). The `staff_attrition_summary` view exposes
per-methodology measures only; no generic blendable rate exists.

**Tech Stack:** BigQuery, dbt 1.9+ (kipptaf project), Cube YAML (`src/cube/`),
sqlfluff BigQuery dialect, trunk pre-commit/pre-push hooks.

## Global Constraints

- All dbt runs: `uv run dbt ... --project-dir src/dbt/kipptaf`
- Dev builds: add `--target dev --defer --state src/dbt/kipptaf/target/prod`
- Never `--target prod` — hand prod runs to the user
- Marts inherit `contract: enforced: true` and `materialized: view` from
  `dbt_project.yml` — do not restate them per model
- All generic dbt tests require `arguments:` nesting (dbt 1.11+)
- sqlfluff ST09: ON-clause predicates list the earlier-referenced table on the
  left
- sqlfluff ST06: column ordering within SELECT (plain refs → constants → simple
  functions → nested → logicals → case → window)
- sqlfluff CV03: trailing comma on every last column in a SELECT clause;
  `select *,` for pass-through CTEs; enumerate columns in UNION branches (no
  `select *`)
- Surrogate key column `type` is a BigQuery reserved word — backtick in SQL
  (`` `type` ``), `quote: true` in YAML
- No `ORDER BY` in mart SQL; no `GROUP BY ALL`
- Cube cubes: `public: false`; views: `public: true` (inherited, not stated)
- Cube naming: `name:` matches filename, no `fct_`/`dim_` prefix
- Cube `sql_table` always `kipptaf_marts.<table>`
- Trunk pre-commit runs `fmt` only; sqlfluff/yamllint fire at pre-push/CI — run
  `/workspaces/teamster/.trunk/tools/trunk check --force <files>` from the
  worktree before pushing
- Git staging: `git add -u` (avoid `-A`/`.`); commit messages follow
  conventional commits

---

## File Map

| Action | Path                                                                    | Change                                                          |
| ------ | ----------------------------------------------------------------------- | --------------------------------------------------------------- |
| Modify | `src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql`            | DRY refactor + new columns                                      |
| Modify | `src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml` | New columns, updated PK description, drop `staff_status_key` FK |
| Create | `src/cube/model/cubes/staff/staff_attrition.yml`                        | New fact cube                                                   |
| Create | `src/cube/model/cubes/conformed/attrition_periods.yml`                  | Trend-spine cube (`extends: dates`)                             |
| Create | `src/cube/model/views/staff/staff_attrition_summary.yml`                | Analyst-facing summary view                                     |
| Modify | `src/dbt/kipptaf/models/exposures/cube.yml`                             | Add `staff_attrition_summary` to Cube exposure                  |

---

## Task 1: dbt — DRY CTE refactor + new columns

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml`

**Interfaces:**

- Produces: `fct_staff_attrition` with columns `staff_attrition_key` (PK),
  `staff_key`, `academic_year`, `type` (quoted reserved word),
  `window_start_date`, `window_close_date`, `as_of_exit_date`, `is_attrition`,
  `termination_effective_date`, `termination_reason`, `termination_type`,
  `cutoff_date`
- Removes: `staff_status_key` (the `dim_staff_status` FK — no longer needed;
  exit context comes through the Cube join to `staff_work_history`)

- [ ] **Step 1: Verify behavioral baseline**

  Count rows by `(type, academic_year, is_attrition)` in the CURRENT
  `fct_staff_attrition` for completed years. Record these numbers — the refactor
  must reproduce them exactly (except ≈8 artifact-reason rows whose reason label
  changes).

  ```bash
  uv run --with google-cloud-bigquery python - <<'EOF'
  from google.cloud import bigquery
  c = bigquery.Client()
  rows = c.query("""
    select
      `type`,
      academic_year,
      is_attrition,
      count(*) as n,
    from `teamster-332318.kipptaf_marts.fct_staff_attrition`
    where academic_year < 2025
    group by `type`, academic_year, is_attrition
    order by `type`, academic_year, is_attrition
  """).result()
  for r in rows: print(dict(r))
  EOF
  ```

  Save the output — you will diff against it in Step 6.

- [ ] **Step 2: Replace `fct_staff_attrition.sql` with the DRY refactor**

  Replace the entire file content with:

  ```sql
  with
      /* Per-employee assignment-status timeline. Sourced from
         dim_work_assignment_status (status SCD), filtered to primary,
         non-Intern assignments via inner joins to
         dim_work_assignment_primary and dim_work_assignment_jobs.
         dim_staff_work_assignments resolves item_id -> staff_key, and
         dim_staff resolves staff_key -> employee_number via staff_unique_id.

         Limitation: pre-2021 NJ Dayforce-era staff are not covered. The
         retired int_people__staff_roster_history chain unioned Dayforce
         records; the work-assignment dim family is ADP-only. Restoring
         Dayforce coverage requires unioning into the upstream dims —
         tracked at #3744. */
      teammate_history as (
          select
              wast.effective_start_date as effective_date_start,
              wast.effective_end_date as effective_date_end,
              wast.effective_start_date as assignment_status_effective_date,
              ds.staff_unique_id as employee_number,
              {{
                  dbt_utils.generate_surrogate_key(["ds.staff_unique_id"])
              }} as staff_key,
              wast.status_code,
              wast.reason_name,

              {{
                  date_to_fiscal_year(
                      date_field="wast.effective_start_date",
                      start_month=7,
                      year_source="start",
                  )
              }} as academic_year,
          from {{ ref("dim_work_assignment_status") }} as wast
          inner join
              {{ ref("dim_work_assignment_primary") }} as wap
              on wast.work_assignment_key = wap.work_assignment_key
              and wast.effective_start_date <= wap.effective_end_date
              and wast.effective_end_date >= wap.effective_start_date
              and wap.is_primary_position
          inner join
              {{ ref("dim_work_assignment_jobs") }} as waj
              on wast.work_assignment_key = waj.work_assignment_key
              and wast.effective_start_date <= waj.effective_end_date
              and wast.effective_end_date >= waj.effective_start_date
              and waj.position_title != 'Intern'
          inner join
              {{ ref("dim_staff_work_assignments") }} as swa
              on wast.work_assignment_key = swa.work_assignment_key
          inner join {{ ref("dim_staff") }} as ds on swa.staff_key = ds.staff_key
      ),

      -- one row per methodology; the only thing that differs between types
      windows as (
          select *
          from
              unnest(
                  [
                      struct(
                          'foundation' as attrition_type,
                          9 as start_month, 1 as start_day,
                          4 as close_month, 30 as close_day,
                          9 as check_month, 1 as check_day
                      ),
                      struct('nj_compliance', 7, 1, 6, 30, 7, 1),
                      struct('recruitment', 9, 1, 8, 31, 9, 1)
                  ]
              )
      ),

      academic_years as (select distinct academic_year from teammate_history),

      -- denominator: active (non-'T') with effective span overlapping the window
      year_cohort as (
          select distinct w.attrition_type, ay.academic_year, th.employee_number, th.staff_key,
          from academic_years as ay
          cross join windows as w
          inner join
              teammate_history as th
              on th.effective_date_start
              <= date(ay.academic_year + 1, w.close_month, w.close_day)
              and th.effective_date_end
              >= date(ay.academic_year, w.start_month, w.start_day)
          where th.status_code != 'T'
      ),

      -- returners: active (non-'T') on the type's return-check date
      returner_cohort as (
          select distinct w.attrition_type, ay.academic_year, th.employee_number,
          from academic_years as ay
          cross join windows as w
          inner join
              teammate_history as th
              on date(ay.academic_year + 1, w.check_month, w.check_day)
              between th.effective_date_start and th.effective_date_end
          where th.status_code != 'T'
      ),

      -- first REAL termination within the window (artifact reasons excluded so a
      -- genuine reason wins the rn=1 pick when both exist)
      terminations as (
          select
              w.attrition_type,
              ay.academic_year,
              th.employee_number,
              th.reason_name as termination_reason,
              th.assignment_status_effective_date as termination_effective_date,
              row_number() over (
                  partition by w.attrition_type, ay.academic_year, th.employee_number
                  order by th.assignment_status_effective_date asc
              ) as rn,
          from academic_years as ay
          cross join windows as w
          inner join
              teammate_history as th
              on th.assignment_status_effective_date
              between date(ay.academic_year, w.start_month, w.start_day)
              and date(ay.academic_year + 1, w.close_month, w.close_day)
          where
              th.status_code = 'T'
              and coalesce(th.reason_name, '') not in (
                  'Import Created Action', 'Upgrade Created Action', 'Internship Ended'
              )
      ),

      -- last ACTIVE primary-assignment start on/before departure: the anchor for
      -- resolving as-of-exit work context. Assignment-level (aligns with
      -- staff_work_history periods) and capped at the term date so a stray
      -- post-termination "active" row can't win.
      as_of as (
          select
              yc.attrition_type,
              yc.academic_year,
              yc.employee_number,
              max(th.effective_date_start) as as_of_exit_date,
          from year_cohort as yc
          inner join windows as w on yc.attrition_type = w.attrition_type
          left join
              terminations as t
              on yc.attrition_type = t.attrition_type
              and yc.employee_number = t.employee_number
              and yc.academic_year = t.academic_year
              and t.rn = 1
          inner join
              teammate_history as th
              on th.employee_number = yc.employee_number
              and th.status_code != 'T'
              and th.effective_date_start
              between date(yc.academic_year, w.start_month, w.start_day) and coalesce(
                  t.termination_effective_date,
                  date(yc.academic_year + 1, w.close_month, w.close_day)
              )
          group by yc.attrition_type, yc.academic_year, yc.employee_number
      ),

      attrition as (
          select
              yc.attrition_type,
              yc.academic_year,
              yc.employee_number,
              yc.staff_key,

              if(rc.employee_number is null, true, false) as is_attrition,

              -- window bounds drive the period-spine join in Cube
              date(yc.academic_year, w.start_month, w.start_day) as window_start_date,
              date(
                  yc.academic_year + 1, w.close_month, w.close_day
              ) as window_close_date,

              if(
                  rc.employee_number is null, t.termination_effective_date, null
              ) as termination_effective_date,
              if(
                  rc.employee_number is null, t.termination_reason, null
              ) as termination_reason,
              if(
                  rc.employee_number is null,
                  t.termination_effective_date,
                  date(yc.academic_year + 1, w.close_month, w.close_day)
              ) as attrition_cutoff_date,

              ao.as_of_exit_date,
          from year_cohort as yc
          inner join windows as w on yc.attrition_type = w.attrition_type
          left join
              returner_cohort as rc
              on yc.attrition_type = rc.attrition_type
              and yc.employee_number = rc.employee_number
              and yc.academic_year = rc.academic_year
          left join
              terminations as t
              on yc.attrition_type = t.attrition_type
              and yc.employee_number = t.employee_number
              and yc.academic_year = t.academic_year
              and t.rn = 1
          left join
              as_of as ao
              on yc.attrition_type = ao.attrition_type
              and yc.employee_number = ao.employee_number
              and yc.academic_year = ao.academic_year
      ),

      -- derive termination_type from the leading token of the reason string;
      -- a named CTE (not inline CASE in a select list) per marts conventions
      classified as (
          select
              *,
              case
                  when termination_reason is null then null
                  when starts_with(termination_reason, 'Resignation') then 'Resignation'
                  when starts_with(termination_reason, 'Termination') then 'Termination'
                  when
                      starts_with(termination_reason, 'Non-Renewal')
                      or starts_with(termination_reason, 'NonRenewal')
                  then 'Non-Renewal'
                  else 'Other'
              end as termination_type,
          from attrition
      )

  select
      {{
          dbt_utils.generate_surrogate_key(
              ["c.employee_number", "c.academic_year", "c.attrition_type"]
          )
      }} as staff_attrition_key,

      c.staff_key,

      c.academic_year,
      c.attrition_type as `type`,
      c.window_start_date,
      c.window_close_date,
      c.as_of_exit_date,
      c.attrition_cutoff_date as cutoff_date,
      c.is_attrition,
      c.termination_effective_date,
      c.termination_reason,
      c.termination_type,
  from classified as c
  ```

- [ ] **Step 3: Update `fct_staff_attrition.yml`**

  Replace the entire file content with:

  ```yaml
  models:
    - name: fct_staff_attrition
      description: >-
        Staff attrition fact. One row per employee x academic_year x
        attrition_type (foundation, nj_compliance, recruitment). is_attrition is
        true when the employee was in a primary, non-Intern, Active assignment
        during the year window but did not return by the methodology's
        return-check date. Source-of-truth is dim_work_assignment_status
        (assignment-status SCD) intersected with dim_work_assignment_primary and
        dim_work_assignment_jobs, joined to dim_staff_work_assignments and
        dim_staff. Coverage limitation — pre-2021 NJ Dayforce-era staff are not
        included (ADP-only source dims); tracked at #3744.
      columns:
        - name: staff_attrition_key
          data_type: string
          description: >-
            Surrogate primary key: generate_surrogate_key(["employee_number",
            "academic_year", "attrition_type"]).
          constraints:
            - type: primary_key
              warn_unsupported: false
          data_tests:
            - unique
            - not_null

        - name: staff_key
          data_type: string
          description: >-
            Surrogate FK to dim_staff and staff_work_history:
            generate_surrogate_key(["employee_number"]). Join key for the
            point-in-time exit-context join in the staff_attrition Cube cube.
            Also used as the count_distinct measure key.
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

        - name: academic_year
          data_type: int64
          description: >-
            Academic year the attrition window belongs to. Derived from the
            fiscal year starting July of that year (e.g., 2024 = July 2024 -
            June 2025).

        - name: type
          quote: true
          data_type: string
          description: >-
            Attrition methodology — foundation (9/1-4/30 window, return check
            9/1), nj_compliance (7/1-6/30 window, return check 7/1), or
            recruitment (9/1-8/31 window, return check 9/1 of following year).
          data_tests:
            - accepted_values:
                arguments:
                  values: [foundation, nj_compliance, recruitment]

        - name: window_start_date
          data_type: date
          description: >-
            First day of the attrition window for this methodology and academic
            year.

        - name: window_close_date
          data_type: date
          description: >-
            Last day of the attrition window for this methodology and academic
            year.

        - name: as_of_exit_date
          data_type: date
          description: >-
            Date of the last active (non-Terminated) primary-assignment record
            that falls within the attrition window, capped at the termination
            effective date. Used as the point-in-time pin for the
            staff_work_history join in Cube to resolve exit-context work
            attributes (title, department, location). Null when no active
            pre-termination record exists.

        - name: cutoff_date
          data_type: date
          description: >-
            Window close date for retained staff, or termination effective date
            for staff who attrited within the window.

        - name: is_attrition
          data_type: boolean
          description: >-
            TRUE if the staff member did not return by the return-check date for
            this methodology's window.

        - name: termination_effective_date
          data_type: date
          description: >-
            Effective date of the first real termination event within the
            window. Null for retained staff or attritors with no captured
            T-status row.

        - name: termination_reason
          data_type: string
          description: >-
            Assignment-status reason for the first real termination within the
            window (artifact reasons Import Created Action, Upgrade Created
            Action, and Internship Ended are excluded from the pick). Null for
            retained staff or when only artifact reasons were found.

        - name: termination_type
          data_type: string
          description: >-
            Leading token of termination_reason — Resignation, Termination,
            Non-Renewal, or Other. Null when termination_reason is null.
          data_tests:
            - accepted_values:
                arguments:
                  values: [Resignation, Termination, Non-Renewal, Other]
  ```

- [ ] **Step 4: Build and check behavioral equivalence**

  ```bash
  uv run dbt build \
    --select fct_staff_attrition \
    --project-dir src/dbt/kipptaf \
    --target dev \
    --defer --state src/dbt/kipptaf/target/prod
  ```

  Expected: model builds, all tests pass. If tests fail, investigate before
  continuing.

  Then re-run the baseline query from Step 1 against your dev schema
  (`zz_<user>_kipptaf_marts.fct_staff_attrition`) and diff against the saved
  baseline. The only acceptable differences are ≈8 rows where
  `termination_reason` changed from an artifact label to `null` or a real
  reason. Cohort counts (`count(*)` per `type, academic_year, is_attrition`)
  must be identical.

  ```bash
  uv run --with google-cloud-bigquery python - <<'EOF'
  from google.cloud import bigquery
  import subprocess, os
  user = subprocess.check_output(["gcloud","config","get-value","account"],
                                  text=True).strip().split("@")[0].replace(".","")
  schema = f"zz_{user}_kipptaf_marts"
  c = bigquery.Client()
  rows = c.query(f"""
    select
      `type`,
      academic_year,
      is_attrition,
      count(*) as n,
    from `teamster-332318.{schema}.fct_staff_attrition`
    where academic_year < 2025
    group by `type`, academic_year, is_attrition
    order by `type`, academic_year, is_attrition
  """).result()
  for r in rows: print(dict(r))
  EOF
  ```

- [ ] **Step 5: Lint**

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force \
    src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql \
    src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml
  ```

  Expected: no issues (trunk autoformats on commit; sqlfluff/yamllint fire
  here). Fix any reported issues before proceeding.

- [ ] **Step 6: Commit**

  ```bash
  git add -u
  git commit -m "refactor(dbt): DRY fct_staff_attrition — windows unnest, as_of_exit_date, staff_key, termination_type"
  ```

---

## Task 2: Cube — `attrition_periods` cube (`extends: dates`)

**Files:**

- Create: `src/cube/model/cubes/conformed/attrition_periods.yml`

**Interfaces:**

- Produces: cube `attrition_periods` that inherits all `dates` dimensions
  (`date_day`, `academic_year`, `calendar_week_end_date`,
  `school_week_end_date`, `month_name`, `month_number`) for use as the trend
  axis in `staff_attrition`.
- Consumed by: `staff_attrition` cube (one_to_many join on the period window).

- [ ] **Step 1: Create `attrition_periods.yml`**

  ```yaml
  cubes:
    - name: attrition_periods
      public: false
      # Trend-axis alias for the staff_attrition cube. Extends dates so it
      # inherits all dim_dates dimensions (calendar_week_end_date,
      # school_week_end_date, academic_year, month_name, etc.) while remaining
      # a distinct cube entity — staff_work_history already joins the original
      # dates cube, so routing the trend through this alias avoids a diamond.
      extends: dates
  ```

- [ ] **Step 2: Verify `dates` cube has no outward joins**

  Open `src/cube/model/cubes/conformed/dates.yml` and confirm there is no
  `joins:` block. The `extends: dates` copy must not inherit any joins pointing
  back to a parent cube that `staff_work_history` also joins — that would
  recreate the diamond. If a `joins:` block exists on `dates`, do NOT use
  `extends: dates`; instead use `sql_table: kipptaf_marts.dim_dates` directly
  with the dimensions you need listed explicitly.

- [ ] **Step 3: Lint**

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force \
    src/cube/model/cubes/conformed/attrition_periods.yml
  ```

  Expected: no issues.

- [ ] **Step 4: Commit**

  ```bash
  git add src/cube/model/cubes/conformed/attrition_periods.yml
  git commit -m "feat(cube): add attrition_periods cube (extends dates) for attrition trend axis"
  ```

---

## Task 3: Cube — `staff_attrition` cube

**Files:**

- Create: `src/cube/model/cubes/staff/staff_attrition.yml`

**Interfaces:**

- Consumes: `kipptaf_marts.fct_staff_attrition` (from Task 1);
  `staff_work_history` cube (point-in-time join on `staff_key` +
  `as_of_exit_date`); `attrition_periods` cube (trend spine, one_to_many range
  join on `window_start_date`/`window_close_date`).
- Produces: cube `staff_attrition` with 12 measures (4 per methodology × 3) and
  dimensions `attrition_methodology`, `termination_reason`, `termination_type`,
  `termination_effective_date`, `is_attrition`, `academic_year`. Non-public
  backing dims (`staff_key`, `window_start_date`, `window_close_date`,
  `as_of_exit_date`).

- [ ] **Step 1: Create `staff_attrition.yml`**

  ```yaml
  cubes:
    - name: staff_attrition
      public: false
      sql_table: kipptaf_marts.fct_staff_attrition

      joins:
        # Point-in-time exit context — the staff-domain hub cube.
        # All work/location/region/manager/demographic context traverses from
        # here, exactly as staff_detail composes them. many_to_one: one exit
        # period per attrition row (capped by as_of_exit_date).
        - name: staff_work_history
          relationship: many_to_one
          sql: >
            {staff_work_history.staff_key} = {CUBE}.staff_key AND
            {CUBE}.as_of_exit_date
              BETWEEN CAST({staff_work_history.effective_start_date} AS DATE)
              AND CAST({staff_work_history.effective_end_date} AS DATE)
            AND {staff_work_history.is_primary_position} = true

        # Trend axis — attrition_periods extends dates, so it is a distinct cube
        # from staff_work_history.dates. one_to_many: one cohort row fans out
        # across all dates in its window; count_distinct(staff_key) deduplicates.
        - name: attrition_periods
          relationship: one_to_many
          sql: >
            CAST({attrition_periods.date_day} AS DATE)
              BETWEEN {CUBE}.window_start_date
              AND LEAST({CUBE}.window_close_date, CURRENT_DATE())

      dimensions:
        - name: attrition_methodology
          description: >-
            Attrition methodology — foundation, nj_compliance, or recruitment.
            Each methodology uses a different cohort window and return-check
            date. Never mix methodologies in one calculation — use the
            per-methodology measures instead.
          sql: "{CUBE}.type"
          type: string
          public: true

        - name: termination_reason
          description: >-
            Full compound reason string for the first real termination within
            the window (e.g., "Resignation - Regrettable - Career Change"). Null
            for retained staff or when only artifact reasons exist. About 25% of
            attritors have a null reason (no captured T-status row) — treat null
            as an Unknown bucket in any reason breakdown.
          sql: termination_reason
          type: string
          public: true

        - name: termination_type
          description: >-
            Leading token of termination_reason — Resignation, Termination,
            Non-Renewal, or Other. Null follows the same rule as
            termination_reason.
          sql: termination_type
          type: string
          public: true

        - name: termination_effective_date
          description: >-
            Date of the first real termination event within the window. Null for
            retained staff or no-T-row attritors.
          sql: CAST(termination_effective_date AS TIMESTAMP)
          type: time
          public: true

        - name: is_attrition
          description: >-
            TRUE if the staff member did not return by the methodology's
            return-check date. The denominator for all attrition rates includes
            both TRUE and FALSE rows (the full cohort).
          sql: is_attrition
          type: boolean
          public: true

        - name: academic_year
          description: >-
            Academic year of the attrition window (July start; 2024 = 2024-25
            school year). Filter to a single academic_year for point-in-time
            rates.
          sql: academic_year
          type: number
          public: true

        # Backing dimensions — support joins, not analyst-facing
        - name: staff_key
          description: Surrogate key to dim_staff and staff_work_history.
          sql: staff_key
          type: string
          primary_key: true

        - name: window_start_date
          description:
            First day of the attrition window. Backs the attrition_periods join.
          sql: CAST(window_start_date AS TIMESTAMP)
          type: time

        - name: window_close_date
          description:
            Last day of the attrition window. Backs the attrition_periods join.
          sql: CAST(window_close_date AS TIMESTAMP)
          type: time

        - name: as_of_exit_date
          description: Pin date for the staff_work_history point-in-time join.
          sql: CAST(as_of_exit_date AS TIMESTAMP)
          type: time

      measures:
        # ── Foundation ─────────────────────────────────────────────────────────
        - name: count_cohort_foundation
          description: >-
            Foundation cohort size — staff active between 9/1 and 4/30 of the
            academic year (the denominator for foundation attrition rate).
          sql: staff_key
          type: count_distinct
          filters:
            - sql: "{CUBE}.type = 'foundation'"
          public: true

        - name: count_attritors_foundation
          description: >-
            Foundation attritors to date — cohort members who did not return by
            9/1 of the following year and whose termination date falls on or
            before the queried period. With no period grouping, equals the
            final-year count.
          sql: staff_key
          type: count_distinct
          filters:
            - sql: >
                {CUBE}.type = 'foundation' AND {CUBE}.is_attrition = true AND (
                  {CUBE}.termination_effective_date IS NULL
                  OR {CUBE}.termination_effective_date
                    <= CAST({attrition_periods.date_day} AS DATE)
                )
          public: true

        - name: attrition_rate_foundation
          description: >-
            Foundation attrition rate — count_attritors_foundation /
            count_cohort_foundation. Add attrition_periods granularity for a
            cumulative trend; omit for final-outcome rate.
          sql: >
            {count_attritors_foundation} / NULLIF({count_cohort_foundation}, 0)
          type: number
          format: percent
          public: true

        - name: retention_rate_foundation
          description:
            Foundation retention rate — 1 minus attrition_rate_foundation.
          sql: "1 - {attrition_rate_foundation}"
          type: number
          format: percent
          public: true

        # ── NJ Compliance ──────────────────────────────────────────────────────
        - name: count_cohort_nj_compliance
          description: >-
            NJ Compliance cohort size — staff active between 7/1 and 6/30 of the
            academic year (denominator for nj_compliance attrition rate).
          sql: staff_key
          type: count_distinct
          filters:
            - sql: "{CUBE}.type = 'nj_compliance'"
          public: true

        - name: count_attritors_nj_compliance
          description: >-
            NJ Compliance attritors to date — same semantics as
            count_attritors_foundation but scoped to the nj_compliance
            methodology.
          sql: staff_key
          type: count_distinct
          filters:
            - sql: >
                {CUBE}.type = 'nj_compliance' AND {CUBE}.is_attrition = true AND
                (
                  {CUBE}.termination_effective_date IS NULL
                  OR {CUBE}.termination_effective_date
                    <= CAST({attrition_periods.date_day} AS DATE)
                )
          public: true

        - name: attrition_rate_nj_compliance
          description: >-
            NJ Compliance attrition rate — count_attritors_nj_compliance /
            count_cohort_nj_compliance.
          sql: >
            {count_attritors_nj_compliance} /
            NULLIF({count_cohort_nj_compliance}, 0)
          type: number
          format: percent
          public: true

        - name: retention_rate_nj_compliance
          description:
            NJ Compliance retention rate — 1 minus attrition_rate_nj_compliance.
          sql: "1 - {attrition_rate_nj_compliance}"
          type: number
          format: percent
          public: true

        # ── Recruitment ────────────────────────────────────────────────────────
        - name: count_cohort_recruitment
          description: >-
            Recruitment cohort size — staff active between 9/1 and 8/31 of the
            academic year (denominator for recruitment attrition rate).
          sql: staff_key
          type: count_distinct
          filters:
            - sql: "{CUBE}.type = 'recruitment'"
          public: true

        - name: count_attritors_recruitment
          description: >-
            Recruitment attritors to date — same semantics as
            count_attritors_foundation but scoped to the recruitment
            methodology.
          sql: staff_key
          type: count_distinct
          filters:
            - sql: >
                {CUBE}.type = 'recruitment' AND {CUBE}.is_attrition = true AND (
                  {CUBE}.termination_effective_date IS NULL
                  OR {CUBE}.termination_effective_date
                    <= CAST({attrition_periods.date_day} AS DATE)
                )
          public: true

        - name: attrition_rate_recruitment
          description: >-
            Recruitment attrition rate — count_attritors_recruitment /
            count_cohort_recruitment.
          sql: >
            {count_attritors_recruitment} / NULLIF({count_cohort_recruitment},
            0)
          type: number
          format: percent
          public: true

        - name: retention_rate_recruitment
          description:
            Recruitment retention rate — 1 minus attrition_rate_recruitment.
          sql: "1 - {attrition_rate_recruitment}"
          type: number
          format: percent
          public: true
  ```

- [ ] **Step 2: Lint**

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force \
    src/cube/model/cubes/staff/staff_attrition.yml
  ```

  Expected: no issues.

- [ ] **Step 3: Commit**

  ```bash
  git add src/cube/model/cubes/staff/staff_attrition.yml
  git commit -m "feat(cube): add staff_attrition cube with per-methodology measures and period-spine join"
  ```

---

## Task 4: Cube — `staff_attrition_summary` view + exposure update

**Files:**

- Create: `src/cube/model/views/staff/staff_attrition_summary.yml`
- Modify: `src/dbt/kipptaf/models/exposures/cube.yml`

**Interfaces:**

- Consumes: `staff_attrition` cube (all 12 measures + attrition dims); traversal
  of `staff_work_history.staff`, `.locations`, `.locations.regions` for
  demographic/location breakdowns; `attrition_periods` (trend dims).
- Produces: public `staff_attrition_summary` view — analyst-facing aggregate
  surface. No direct staff identifiers; `attrition_methodology` is not a free
  dimension (encoded in measure names).

- [ ] **Step 1: Create `staff_attrition_summary.yml`**

  ```yaml
  views:
    - name: staff_attrition_summary
      description: >-
        Aggregate staff attrition rates by methodology, termination reason/type,
        work-context breakdowns, and trend. No direct staff identifiers.

        Each methodology uses a different cohort window and denominator —
        foundation (9/1-4/30), nj_compliance (7/1-6/30), recruitment (9/1-8/31).
        Use the per-methodology measures (e.g., attrition_rate_foundation)
        rather than mixing methodologies in one query. Filter academic_year for
        a single year; omit period grouping for a final-outcome rate, or group
        by attrition_periods_calendar_week_end_date /
        attrition_periods_school_week_end_date / attrition_periods_date_day
        (with granularity month) for a cumulative trend.

        About 25% of attritors have null termination_reason — treat null as an
        Unknown bucket in reason/type breakdowns.

      cubes:
        - join_path: staff_attrition
          includes:
            - count_cohort_foundation
            - count_attritors_foundation
            - attrition_rate_foundation
            - retention_rate_foundation
            - count_cohort_nj_compliance
            - count_attritors_nj_compliance
            - attrition_rate_nj_compliance
            - retention_rate_nj_compliance
            - count_cohort_recruitment
            - count_attritors_recruitment
            - attrition_rate_recruitment
            - retention_rate_recruitment
            - termination_reason
            - termination_type
            - termination_effective_date
            - is_attrition
            - academic_year

        - join_path: staff_attrition.attrition_periods
          prefix: true
          includes:
            - date_day
            - academic_year
            - month_name
            - month_number
            - calendar_week_end_date
            - school_week_end_date

        - join_path: staff_attrition.staff_work_history
          includes:
            - position_title
            - job_code
            - worker_type
            - department_name
            - business_unit_name
            - is_management_position

        - join_path: staff_attrition.staff_work_history.staff
          prefix: false
          includes:
            - gender_identity
            - race
            - is_hispanic

        - join_path: staff_attrition.staff_work_history.locations
          prefix: true
          includes:
            - location_name
            - abbreviation
            - grade_band
            - campus
            - city

        - join_path: staff_attrition.staff_work_history.locations.regions
          prefix: true
          includes:
            - region_name
            - state

      meta:
        folders:
          - name: Foundation
            members:
              - count_cohort_foundation
              - count_attritors_foundation
              - attrition_rate_foundation
              - retention_rate_foundation
          - name: NJ Compliance
            members:
              - count_cohort_nj_compliance
              - count_attritors_nj_compliance
              - attrition_rate_nj_compliance
              - retention_rate_nj_compliance
          - name: Recruitment
            members:
              - count_cohort_recruitment
              - count_attritors_recruitment
              - attrition_rate_recruitment
              - retention_rate_recruitment
          - name: Termination
            members:
              - termination_reason
              - termination_type
              - termination_effective_date
              - is_attrition
          - name: Period
            members:
              - academic_year
              - attrition_periods_date_day
              - attrition_periods_academic_year
              - attrition_periods_month_name
              - attrition_periods_month_number
              - attrition_periods_calendar_week_end_date
              - attrition_periods_school_week_end_date
          - name: Work Context
            members:
              - position_title
              - job_code
              - worker_type
              - department_name
              - business_unit_name
              - is_management_position
          - name: Location
            members:
              - locations_location_name
              - locations_abbreviation
              - locations_grade_band
              - locations_campus
              - locations_city
              - regions_region_name
              - regions_state
          - name: Staff
            members:
              - gender_identity
              - race
              - is_hispanic

      access_policy:
        # No direct identifiers — demographic breakdowns only.
        # Low-n suppression tracked at #4237.
        - group: cube-access-staff-data
          member_level:
            includes: "*"
  ```

- [ ] **Step 2: Update `cube.yml` exposure**

  Open `src/dbt/kipptaf/models/exposures/cube.yml`. Locate the
  `cube_semantic_layer.depends_on` block (the list of `ref(...)` entries). Add
  `staff_attrition_summary` to that block. The fact itself
  (`fct_staff_attrition`) is already listed — do not duplicate it. The new line
  to add:

  ```yaml
  - ref("staff_attrition_summary")
  ```

  Wait — `cube.yml` references mart `ref()` values (dbt models), not Cube view
  names. Check what other entries look like:

  ```bash
  grep -A 5 "cube_semantic_layer" src/dbt/kipptaf/models/exposures/cube.yml | head -20
  ```

  The exposure's `depends_on` lists dbt models that Cube reads.
  `fct_staff_attrition` is already there. No new dbt model was added in this PR
  (the Cube view `staff_attrition_summary` reads `fct_staff_attrition` which is
  already listed). **No change needed to `cube.yml`** unless the existing entry
  is missing — verify with the grep output and skip the edit if
  `ref("fct_staff_attrition")` is present.

- [ ] **Step 3: Lint both files**

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force \
    src/cube/model/views/staff/staff_attrition_summary.yml
  ```

  Expected: no issues.

- [ ] **Step 4: Commit**

  ```bash
  git add src/cube/model/views/staff/staff_attrition_summary.yml
  git commit -m "feat(cube): add staff_attrition_summary view"
  ```

---

## Task 5: Prototype validation (Cube dev server)

Validation requires the user to run the Cube dev server — Claude cannot launch
long-running servers.

**Files:** No file changes in this task (validation only; `sql_table` temp
redirect is reverted before committing).

**Pre-check:** Task 1 must be complete (dev schema table exists). Tasks 2–4 must
be committed to the branch.

- [ ] **Step 1: Redirect `sql_table` temporarily for dev testing**

  In `src/cube/model/cubes/staff/staff_attrition.yml`, temporarily change:

  ```yaml
  sql_table: kipptaf_marts.fct_staff_attrition
  ```

  to your dev schema table (do **not** commit this change):

  ```yaml
  sql_table: zz_<your_username>_kipptaf_marts.fct_staff_attrition
  ```

  Replace `<your_username>` with the GCP account prefix from
  `gcloud config get-value account` (dots replaced with underscores).

- [ ] **Step 2: Ask the user to start the Cube dev server**

  The VS Code task is `Cube: Dev Server` (defined in `.vscode/tasks.json`). Ask:

  > "Can you start the `Cube: Dev Server` VS Code task and let me know when the
  > playground is ready? I need to run validation queries against the dev
  > branch."

- [ ] **Step 3: Validate in the Cube Playground**

  Once the dev server is running, the user can open the playground
  (http://localhost:4000). Run these validation queries in the Cube REST
  explorer or the Playground query builder:

  **V1 — Final-outcome rate (no trend, completed year):**

  ```json
  {
    "measures": [
      "staff_attrition_summary.attrition_rate_foundation",
      "staff_attrition_summary.count_cohort_foundation",
      "staff_attrition_summary.count_attritors_foundation"
    ],
    "filters": [
      {
        "member": "staff_attrition_summary.academic_year",
        "operator": "equals",
        "values": ["2023"]
      }
    ]
  }
  ```

  Expected: rate matches the prior `fct_staff_attrition` output for AY2023
  foundation attrition (from the baseline in Task 1, Step 1).

  **V2 — Weekly trend (monotonically non-decreasing):**

  ```json
  {
    "measures": ["staff_attrition_summary.count_attritors_foundation"],
    "timeDimensions": [
      {
        "dimension": "staff_attrition_summary.attrition_periods_calendar_week_end_date",
        "granularity": "week",
        "dateRange": ["2023-09-01", "2024-04-30"]
      }
    ],
    "filters": [
      {
        "member": "staff_attrition_summary.academic_year",
        "operator": "equals",
        "values": ["2023"]
      }
    ]
  }
  ```

  Expected: cumulative count increases (or stays flat) week-over-week; final
  week equals `count_attritors_foundation` from V1.

  **V3 — School-week grouping works:**

  Same as V2 but `granularity: "week"` on
  `attrition_periods_school_week_end_date`. Expected: similar monotonic trend.

  **V4 — No period grouping = final outcome:**

  ```json
  {
    "measures": [
      "staff_attrition_summary.count_attritors_foundation",
      "staff_attrition_summary.count_cohort_foundation"
    ],
    "filters": [
      {
        "member": "staff_attrition_summary.academic_year",
        "operator": "equals",
        "values": ["2023"]
      }
    ]
  }
  ```

  Expected: counts match V1 (no spine = collapses to final outcome).

  **V5 — Breakdown by `termination_type`:**

  ```json
  {
    "measures": ["staff_attrition_summary.count_attritors_foundation"],
    "dimensions": ["staff_attrition_summary.termination_type"],
    "filters": [
      {
        "member": "staff_attrition_summary.academic_year",
        "operator": "equals",
        "values": ["2023"]
      }
    ]
  }
  ```

  Expected: rows for Resignation, Termination, Non-Renewal, Other, and null. Sum
  of counts = `count_attritors_foundation` from V1.

  **V6 — Work-context breakdown (position_title):**

  ```json
  {
    "measures": ["staff_attrition_summary.count_attritors_foundation"],
    "dimensions": ["staff_attrition_summary.position_title"],
    "filters": [
      {
        "member": "staff_attrition_summary.academic_year",
        "operator": "equals",
        "values": ["2023"]
      }
    ]
  }
  ```

  Expected: rows populated, total = `count_attritors_foundation` from V1.

  **V7 — No diamond (staff_work_history.dates and attrition_periods coexist):**

  Include both a `staff_work_history` dimension and an `attrition_periods` trend
  in one query. If Cube throws "ambiguous member" or "diamond path", there is a
  join-path conflict — investigate before proceeding.

- [ ] **Step 4: Revert the `sql_table` redirect**

  In `src/cube/model/cubes/staff/staff_attrition.yml`, revert:

  ```yaml
  sql_table: kipptaf_marts.fct_staff_attrition
  ```

  Do **not** commit the dev redirect.

- [ ] **Step 5: Document any issues found**

  If any validation query failed or produced unexpected results, document what
  failed and how it was resolved before moving to Task 6.

---

## Task 6: Push and CI

- [ ] **Step 1: Final lint sweep**

  ```bash
  /workspaces/teamster/.trunk/tools/trunk check --force \
    src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql \
    src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml \
    src/cube/model/cubes/conformed/attrition_periods.yml \
    src/cube/model/cubes/staff/staff_attrition.yml \
    src/cube/model/views/staff/staff_attrition_summary.yml
  ```

  Expected: no issues on all five files.

- [ ] **Step 2: Verify `sql_table` is NOT pointing to a dev schema**

  ```bash
  grep -n "zz_" src/cube/model/cubes/staff/staff_attrition.yml
  ```

  Expected: no output. If any `zz_` appears, revert the line before pushing.

- [ ] **Step 3: Push branch**

  ```bash
  git push origin cristinabaldor/feat/claude-staff-attrition-cube-views
  ```

- [ ] **Step 4: Monitor dbt Cloud CI**

  Watch the PR's dbt Cloud CI run. It runs
  `dbt build --select state:modified+ --full-refresh --target staging`. Check
  both CI surfaces:

  - dbt Cloud commit status: `mcp__github__pull_request_read get_status` on the
    PR
  - Trunk/CodeQL check runs:
    `gh api repos/TEAMSchools/teamster/commits/<sha>/check-runs`

  If CI fails on `fct_staff_attrition` with a contract error, compare
  `INFORMATION_SCHEMA.COLUMNS` on the staging model to the YAML — a column
  data_type mismatch is the most likely cause.

- [ ] **Step 5: Check CI for warnings after green**

  ```bash
  # Get the CI run ID from the dbt Cloud status URL, then:
  # mcp__dbt__get_job_run_error(run_id=<id>, warning_only=true)
  ```

  Review any new warnings. Pre-existing relationship warnings on unrelated
  models are expected noise; new warnings on `fct_staff_attrition` need
  investigation.
