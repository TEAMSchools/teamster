# Point-in-time Daily Student Enrollment Metric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a point-in-time daily student-enrollment headcount to the Cube
semantic layer that reconciles with the topline `Total Enrollment` metric and
answers day-exact questions like "what was enrollment on October 1."

**Architecture:** A new dbt mart `fct_student_enrollment_daily` expands
enrollment stints against each school's in-session calendar (one row per
student-stint × in-session day), stamping per-school period-end anchors. A new
Cube `student_enrollment_daily` reads that mart and is governed by the existing
`cube.js` snapshot-anchor guard so its bare `count_students` is always a
point-in-time snapshot. Two views (summary + PII-gated detail) expose it. The
existing stint measure `student_enrollments.count_students` is renamed
`count_enrollments` to free the honest name for the new cube.

**Tech Stack:** dbt (BigQuery), Cube (YAML data models + `cube.js`), the
existing `dim_student_enrollments` / `dim_students` / `dim_locations` /
`dim_dates` star schema.

**Spec:**
[`docs/superpowers/specs/2026-06-08-daily-enrollment-metric-design.md`](../specs/2026-06-08-daily-enrollment-metric-design.md)
(GitHub issue [#4138](https://github.com/TEAMSchools/teamster/issues/4138)).

---

## Spec reconciliations discovered during planning (read first)

Three facts from the warehouse (verified 2026-06-10) refine the spec. None
changes the design; they make tentative spec instructions concrete.

0. **`stg_powerschool__calendar_day` and `stg_powerschool__terms` carry only
   `_dbt_source_relation`, NOT `_dbt_source_project`** — they are
   `union_relations` views. Cross-union joins to them therefore use the repo's
   canonical `union_dataset_join_clause(left_alias=..., right_alias=...)` macro
   (regexp-extracts the `kipp*` prefix from `_dbt_source_relation`), and the
   window partitions use `extract_code_location("<alias>")` to derive a
   `code_location` from the same source. Only
   `int_powerschool__student_enrollment_union` and `stg_powerschool__schools`
   carry `_dbt_source_project` (so the `schoolid → location_key` join to
   `stg_powerschool__schools` uses `_dbt_source_project` equality, unchanged
   from `dim_student_enrollments`). This was implemented in Task 2 and verified
   (17.9M rows, correct grain, 10,637 distinct students on 2025-10-01).

1. **`stg_powerschool__terms` has no `academic_year` column** — only `yearid`.
   The KIPP academic year is `yearid + 1990` (confirmed: min 2002, max 2026).
   The spec's "join the calendar day to `stg_powerschool__terms` ... take the
   term's `academic_year`" therefore derives `academic_year = yearid + 1990`.
2. **`isyearrec = 1` is the deterministic single-term pick** the spec asked for.
   There are exactly 462 `isyearrec = 1` term rows (= `portion = 1` count) — one
   per (school, year), each spanning the school year's full `firstday` →
   `lastday`. Joining the calendar day to the `isyearrec = 1` term row yields
   exactly one academic-year label per day with no fan-out, which is cleaner
   than the spec's tentative "`portion = 4` or `isyearrec = 1`."

Everything else in the spec validated against the warehouse and current code.

4. **Table materialization + `foreign_key` constraints to view-dims is
   unbuildable on BigQuery.** Contract-enforced `materialized: table` emits real
   `references <dim> (...) not enforced` DDL, which BigQuery rejects unless the
   referenced relation declares a PRIMARY KEY — and the parent dims
   (`dim_student_enrollments`, `dim_students`, `dim_locations`) are **views**,
   which can't carry PK constraints. `fct_student_attendance_daily` never hits
   this because it's a view (FK constraints become pure manifest metadata, no
   DDL). Resolution for this table-materialized fact (Task 3): **drop the
   `constraints: foreign_key` blocks; keep the `relationships` data_tests** —
   the tests enforce referential integrity AND capture the `ref()` dependency in
   the DAG (Cube reads joins from its own YAML, not these constraints). Keep the
   PK `constraints: primary_key` block (the `unique`+`not_null` tests back it).

## Working conventions for the implementer

- **Worktree paths**: If this plan runs in a worktree, every `git` call uses
  `git -C <worktree>` and every dbt call uses
  `--project-dir <worktree>/src/dbt/kipptaf`. Run
  `uv run dbt deps --project-dir <worktree>/src/dbt/kipptaf` once before the
  first build (a fresh worktree has no `dbt_packages/`). Paths below are written
  from the main repo root; prepend the worktree path when in a worktree.
- **Python/dbt**: always `uv run dbt ...`, never bare `dbt`.
- **`--target prod` is blocked** for Claude — all builds here use the default
  dev target (writes to `zz_<username>_kipptaf_marts`).
- **Dev builds need defer** for the GCS-external upstreams. Use
  `--defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod` (absolute
  path; relative breaks from a worktree). If `target/prod` is stale, regenerate:
  `uv run dbt parse --target prod --project-dir src/dbt/kipptaf --target-path target/prod`.
- **Trunk**: do not run `trunk fmt`/`check` manually for routine commits — the
  pre-commit/pre-push hooks handle it. For SQL/YAML lint verification before a
  push, run `/workspaces/teamster/.trunk/tools/trunk check --force <files>` with
  cwd set to the worktree (see root CLAUDE.md).
- **Commit cadence**: commit after each task's tests pass. Conventional-commit
  messages (`feat:`, `test:`, `docs:`, `refactor:`).
- **Cube has no local compile.** Cube YAML changes (Tasks 5–8) are validated in
  Cube Cloud Dev Mode after push, not locally. Tasks 5–8 commit the YAML; the
  acceptance/validation against the warehouse happens in Task 9.

---

## File Structure

**Created:**

- `src/dbt/kipptaf/models/marts/facts/fct_student_enrollment_daily.sql` — the
  daily enrollment fact (Task 2).
- `src/dbt/kipptaf/models/marts/facts/properties/fct_student_enrollment_daily.yml`
  — model + column descriptions, contract types, FK/uniqueness tests,
  `materialized: table` override (Task 3).
- `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_latest_record_per_enrollment.sql`
  — singular test (Task 4).
- `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_week_end_per_enrollment_week.sql`
  — singular test (Task 4).
- `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_month_end_per_enrollment_month.sql`
  — singular test (Task 4).
- `src/dbt/kipptaf/tests/fct_student_enrollment_daily__no_null_entrydate_rows.sql`
  — singular test (Task 4).
- `src/cube/model/cubes/students/student_enrollment_daily.yml` — the cube (Task
  6).
- `src/cube/model/views/students/student_enrollment_daily_summary.yml` — summary
  view (Task 7).
- `src/cube/model/views/students/student_enrollment_daily_detail.yml` —
  PII-gated detail view (Task 8).

**Modified:**

- `src/cube/model/cubes/students/student_enrollments.yml` — rename
  `count_students` → `count_enrollments`, add description (Task 5).
- `src/cube/model/views/students/student_enrollments_summary.yml` — rename the
  surfaced measure + fix guidance (Task 5).
- `src/cube/model/views/students/student_enrollments_detail.yml` — rename the
  surfaced measure + fix guidance (Task 5).
- `src/cube/cube.js` — add `student_enrollment_daily` to `SNAPSHOT_CUBES`,
  `count_students` to `SNAPSHOT_MEASURE_STEMS`, `_served`/`_active` to
  `SNAPSHOT_SELF_ANCHORED_SUFFIXES`, and the per-cube anchor override (Task 6).
- `src/dbt/kipptaf/models/exposures/cube.yml` — add the new fact to
  `cube_semantic_layer.depends_on` (Task 3).

**Read-only references (templates — do not modify):**

- `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_daily.sql` — the
  join-shape and anchor-window precedent.
- `src/cube/model/cubes/student_attendance/student_attendance.yml` — cube
  measure/dimension shape.
- `src/cube/model/views/student_attendance/student_attendance_summary.yml` —
  summary view shape.
- `src/cube/model/views/students/student_enrollments_detail.yml` — detail view
  PII-policy shape.

---

## Task 1: Sequence sanity check (no code)

**Files:** none — this is a read/verify gate.

- [ ] **Step 1: Confirm the upstream refs resolve and the branch is current**

Run:

```bash
git -C /workspaces/teamster fetch origin main && git -C /workspaces/teamster merge origin/main
uv run dbt parse --project-dir src/dbt/kipptaf
```

Expected: merge clean (or already up to date); `dbt parse` succeeds with no
error. This confirms `int_powerschool__student_enrollment_union`,
`stg_powerschool__calendar_day`, `stg_powerschool__terms`, `dim_students`,
`dim_locations`, `dim_dates`, and `dim_student_enrollments` all resolve as
`ref()` targets before you build anything.

- [ ] **Step 2: Confirm the prod state manifest exists for defer**

Run:

```bash
ls src/dbt/kipptaf/target/prod/manifest.json
```

Expected: file exists. If missing, run
`uv run dbt parse --target prod --project-dir src/dbt/kipptaf --target-path target/prod`.

---

## Task 2: Build the `fct_student_enrollment_daily` mart SQL

**Files:**

- Create: `src/dbt/kipptaf/models/marts/facts/fct_student_enrollment_daily.sql`

The fact expands stints against each school's in-session calendar, derives the
FK hashes in a CTE (the calendar spine doesn't carry them), sources
`academic_year` from the `isyearrec = 1` term (not the stint), and stamps the
four anchors. The three period anchors are **per-school, `current_date`-capped
last-in-session-day markers** computed with window functions over the expanded
grain; `is_latest_record` is the per-student-stint last enrolled day.

- [ ] **Step 1: Write the model SQL**

Create `src/dbt/kipptaf/models/marts/facts/fct_student_enrollment_daily.sql`:

```sql
with
    -- stints, narrowed to the columns the fact needs; null-entrydate graduate
    -- placeholders are dropped by the half-open join below (entrydate is null
    -- never satisfies cd.date_value >= enr.entrydate)
    enrollments as (
        select
            student_number,
            studentid,
            schoolid,
            entrydate,
            exitdate,
            academic_year,
            enroll_status,
            grade_level,
            _dbt_source_project,
        from {{ ref("int_powerschool__student_enrollment_union") }}
    ),

    -- in-session school days only (the membership grain)
    calendar_days as (
        select schoolid, date_value, _dbt_source_project,
        from {{ ref("stg_powerschool__calendar_day") }}
        where insession = 1 and date_value is not null
    ),

    -- one year-record term per (school, year); yearid + 1990 is the KIPP
    -- academic year. isyearrec = 1 spans the full firstday..lastday and is
    -- unique per (school, year), so the day->term join cannot fan out.
    year_terms as (
        select schoolid, firstday, lastday, _dbt_source_project, yearid + 1990 as academic_year,
        from {{ ref("stg_powerschool__terms") }}
        where isyearrec = 1
    ),

    -- expand: stint x in-session day, label the day's academic year from the
    -- calendar term (not the stint), so date_key and academic_year are
    -- consistent by construction
    expanded as (
        select
            enr.student_number,
            enr.studentid,
            enr.schoolid,
            enr.enroll_status,
            enr.grade_level,
            enr._dbt_source_project,

            cd.date_value as date_key,

            yt.academic_year,
        from enrollments as enr
        inner join
            calendar_days as cd
            on enr.schoolid = cd.schoolid
            and enr._dbt_source_project = cd._dbt_source_project
            and cd.date_value >= enr.entrydate
            and cd.date_value < enr.exitdate
        inner join
            year_terms as yt
            on cd.schoolid = yt.schoolid
            and cd._dbt_source_project = yt._dbt_source_project
            and cd.date_value >= yt.firstday
            and cd.date_value <= yt.lastday
    ),

    -- per-school last in-session day that has actually occurred, by period.
    -- least(period last day, today) caps the in-progress period to today so the
    -- current week/month/year anchor is non-empty (its true last day is future)
    school_period_last_days as (
        select
            schoolid,
            date_key,
            academic_year,
            _dbt_source_project,

            least(
                max(date_key) over (
                    partition by schoolid, _dbt_source_project, academic_year
                ),
                current_date('{{ var("local_timezone") }}')
            ) as _year_last_day,

            least(
                max(date_key) over (
                    partition by
                        schoolid, _dbt_source_project, date_trunc(date_key, month)
                ),
                current_date('{{ var("local_timezone") }}')
            ) as _month_last_day,

            least(
                max(date_key) over (
                    -- trunk-ignore(sqlfluff/LT01): week(monday) special syntax
                    partition by
                        schoolid,
                        _dbt_source_project,
                        date_trunc(date_key, week(monday))
                ),
                current_date('{{ var("local_timezone") }}')
            ) as _week_last_day,
        from expanded
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "spld.student_number",
                "spld._dbt_source_project",
                "spld.date_key",
            ]
        )
    }} as student_enrollment_daily_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "exp.student_number",
                "exp._dbt_source_project",
                "exp.academic_year",
                "exp.entrydate",
            ]
        )
    }} as student_enrollment_key,

    {{ dbt_utils.generate_surrogate_key(["spld.student_number"]) }}
    as student_key,

    sch.location_key,

    spld.date_key,

    spld.academic_year,

    exp.grade_level,

    exp.enroll_status,

    1 as is_enrolled,

    cast(spld.date_key = spld._year_last_day as int64) as is_current_record,
    cast(spld.date_key = spld._month_last_day as int64) as is_month_end_record,
    cast(spld.date_key = spld._week_last_day as int64) as is_week_end_record,

    row_number() over (
        partition by
            spld.student_number, spld._dbt_source_project, spld.academic_year
        order by spld.date_key desc
    )
    = 1 as is_latest_record,
from school_period_last_days as spld
inner join
    expanded as exp
    on spld.student_number = exp.student_number
    and spld._dbt_source_project = exp._dbt_source_project
    and spld.date_key = exp.date_key
left join
    {{ ref("stg_powerschool__schools") }} as sch
    on spld.schoolid = sch.school_number
    and spld._dbt_source_project = sch._dbt_source_project
```

> **Implementer notes (do not paste into the SQL):**
>
> - The `student_enrollment_key` hash inputs must be **byte-identical** to
>   `dim_student_enrollments` and `fct_student_attendance_daily`:
>   `[student_number, _dbt_source_project, academic_year, entrydate]`. `exp`
>   carries `entrydate`? — **No.** `expanded` does not select `entrydate`. **Add
>   `enr.entrydate` to the `expanded` SELECT** (alongside `enr.academic_year`)
>   so the hash compiles — `generate_surrogate_key` over `exp.entrydate` fails
>   with `Name entrydate not found inside exp` otherwise. Add it as a plain
>   column in the `expanded` select list, ordered with the other `enr.*`
>   enumerations.
> - `school_period_last_days` is selected from `expanded`; it must therefore
>   also carry `entrydate` and `enroll_status`/`grade_level` only if the final
>   SELECT reads them from `spld`. The final SELECT reads `grade_level`,
>   `enroll_status`, and `entrydate` from `exp` (the re-join), so `spld` needs
>   only `student_number`, `_dbt_source_project`, `date_key`, `academic_year`,
>   `schoolid`, and the three `_*_last_day` windows. Keep `spld` minimal.
> - **Why re-join `expanded` to `school_period_last_days`?** The window
>   functions in `school_period_last_days` compute per-school period last days
>   over the full expanded grain. Selecting the row attributes (`grade_level`,
>   `enroll_status`, `entrydate` for the hash) from the same CTE is fine — you
>   can collapse the two into one CTE if cleaner. The two-CTE split above is
>   written for clarity; **a single CTE that selects the row columns AND the
>   three windows in one pass is preferred** (avoids the self-join). Rewrite to
>   one CTE: add
>   `student_number, _dbt_source_project, entrydate, grade_level, enroll_status`
>   to the `school_period_last_days` select, drop the `exp` re-join, and read
>   everything from `spld`. Verify the `student_enrollment_key` hash still reads
>   `entrydate` from that CTE.
> - `stg_powerschool__schools` join column: confirm the school PK column name
>   (`school_number` vs `school_id`) and `location_key` presence via
>   `INFORMATION_SCHEMA.COLUMNS` before building — see Step 2. The
>   `dim_student_enrollments` model resolves `location_key` from `schoolid`;
>   mirror exactly how it does so. If `dim_student_enrollments` reaches
>   `location_key` through a different model than `stg_powerschool__schools`,
>   use that model.

- [ ] **Step 2: Verify the school→location_key resolution path before building**

Run (BigQuery MCP or `bq`):

```sql
select column_name, data_type
from `teamster-332318`.`kipptaf_powerschool`.INFORMATION_SCHEMA.COLUMNS
where table_name = 'stg_powerschool__schools'
order by ordinal_position
```

Then open how `dim_student_enrollments` derives `location_key`:

```bash
rg -n 'location_key' src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql
```

Expected: identify the exact model + columns that map `schoolid` →
`location_key`. **Update the `left join` in Step 1 to match
`dim_student_enrollments` exactly** (same model, same join keys). Do not invent
a join — copy the working one.

- [ ] **Step 3: Collapse to a single CTE per the implementer note**

Apply the single-CTE rewrite from the Step 1 notes (drop the self-join; select
row attributes + the three windows in one `school_period_last_days` pass; read
all final columns from `spld`). Re-read the file to confirm the
`student_enrollment_key` hash reads `entrydate` from the surviving CTE.

- [ ] **Step 4: Commit the SQL (no build yet — properties come next)**

```bash
git -C /workspaces/teamster add src/dbt/kipptaf/models/marts/facts/fct_student_enrollment_daily.sql
git -C /workspaces/teamster commit -m "feat(dbt): add fct_student_enrollment_daily mart SQL"
```

---

## Task 3: Add the properties YAML (descriptions, contract, tests, materialization, exposure)

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_enrollment_daily.yml`
- Modify: `src/dbt/kipptaf/models/exposures/cube.yml`

- [ ] **Step 1: Write the properties YAML**

Create
`src/dbt/kipptaf/models/marts/facts/properties/fct_student_enrollment_daily.yml`:

```yaml
models:
  - name: fct_student_enrollment_daily
    description: >-
      Point-in-time student enrollment fact. One row per enrolled student-stint
      per in-session school day, expanded from
      int_powerschool__student_enrollment_union against each school's in-session
      calendar (stg_powerschool__calendar_day, insession = 1). The direct
      day-grain analog of fct_student_attendance_daily, but independent of the
      ADA pipeline so enrollment is complete across all school days.

      This is a complete historical record (alumni and withdrawn students retain
      their real-dated day-rows) — point-in-time-ness is a query concern (date
      filter or period-end anchor), never a row filter. Do NOT filter
      enroll_status to scope alumni; that would break the topline
      reconciliation. Alumni fall out by date.

      academic_year is sourced from the school's year-record calendar term
      (isyearrec = 1, yearid + 1990), so date_key and academic_year are
      consistent by construction — a March 15 row self-labels as the prior-July
      academic year under the KIPP convention with no +1 arithmetic. Location,
      academic year, and date are FK-reachable; region is reached via location
      -> regions, not stored here.
    config:
      materialized: table
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_enrollment_key
              - date_key
    columns:
      - name: student_enrollment_daily_key
        data_type: string
        description: >-
          Surrogate key derived from student_number, _dbt_source_project, and
          date_key. Primary key for this fact.
        constraints:
          - type: primary_key
            warn_unsupported: false
        data_tests:
          - unique
          - not_null

      - name: student_enrollment_key
        data_type: string
        description: >-
          FK to dim_student_enrollments. Surrogate key derived from
          student_number, _dbt_source_project, academic_year, and entrydate.
          Also the partition key for is_latest_record (year-scoped via the
          academic_year input).
        constraints:
          - type: foreign_key
            to: ref('dim_student_enrollments')
            to_columns: [student_enrollment_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_student_enrollments')
                field: student_enrollment_key

      - name: student_key
        data_type: string
        description:
          Surrogate key derived from student_number. FK to dim_students.
        constraints:
          - type: foreign_key
            to: ref('dim_students')
            to_columns: [student_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_students')
                field: student_key

      - name: location_key
        data_type: string
        description: >-
          FK to dim_locations, resolved from schoolid. Null when schoolid does
          not match any location in the crosswalk (e.g., grade_level 99
          placeholder schools), mirroring dim_student_enrollments.
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

      - name: date_key
        data_type: date
        description: >-
          The in-session school day this enrollment row represents. FK to
          dim_dates.
        constraints:
          - type: foreign_key
            to: ref('dim_dates')
            to_columns: [date_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_dates')
                field: date_key

      - name: academic_year
        data_type: int64
        description: >-
          KIPP academic year (July start) of this day, sourced from the school's
          year-record calendar term (isyearrec = 1, yearid + 1990), NOT the
          stint label. The calendar year in which the academic year begins (e.g.
          2025 for the 2025-26 school year, which spans 2025-07-01 to
          2026-06-30).

      - name: grade_level
        data_type: int64
        description: >-
          The grade the student is in. 0 = Kindergarten, -2 = Preschool.
          Degenerate dimension for filtering.

      - name: enroll_status
        data_type: int64
        description: >-
          Enrollment status code: 0 active, 2 withdrawn, 3 graduated.
          STUDENT-LEVEL (current status), identical across all of a student's
          rows — NOT a point-in-time status. Used only by count_students_active.
          Do not use for historical point-in-time counts.

      - name: is_enrolled
        data_type: int64
        description: >-
          1 for every row (each row is one enrolled in-session day). Row marker
          only — measures count_distinct(student_key) rather than summing this,
          because summing across multiple days yields student-days, not a
          headcount.

      - name: is_current_record
        data_type: int64
        description: >-
          1 when date_key is the school's last in-session day of the academic
          year that has actually occurred (least of the school-year last
          in-session day and today). Drives the default point-in-time
          count_students at year / no-grouping grain. Per-school and build-time
          dependent for the in-progress year (shifts as today advances); static
          for completed years.

      - name: is_month_end_record
        data_type: int64
        description: >-
          1 when date_key is the school's last in-session day of the calendar
          month that has actually occurred (least of the month's last in-session
          day and today). Per (school, month). Drives count_students at month
          granularity.

      - name: is_week_end_record
        data_type: int64
        description: >-
          1 when date_key is the school's last in-session day of the ISO week
          (Monday-start) that has actually occurred (least of the week's last
          in-session day and today). Per (school, week). Drives count_students
          at week granularity.

      - name: is_latest_record
        data_type: boolean
        description: >-
          TRUE on each student-stint's last enrolled in-session day of the
          academic year (partitioned by student x district x academic year).
          This is NOT a period-end marker — it exists for anyone ever enrolled,
          so it drives count_students_served (ever-enrolled), not the
          point-in-time default. Keep distinct from is_current_record.
```

> **Implementer note:** `is_current_record` / `is_month_end_record` /
> `is_week_end_record` are `int64` (the SQL casts them with
> `cast(... as int64)`); `is_latest_record` is `boolean` (it's a bare
> `row_number() ... = 1`). This mirrors the attendance fact, where the snapshot
> dims the guard reads are booleans — **but here the guard reads them via the
> cube YAML, which declares its own types.** Keep the fact-column types as
> written (int64 for the three period anchors, boolean for is_latest_record) and
> let the cube YAML (Task 6) cast/declare as the guard needs. If the cube guard
> requires boolean equality (`= true`), Task 6's cube dimension SQL handles the
> presentation; the fact stores int64 0/1 per marts R3.

- [ ] **Step 2: Add the exposure dependency**

In `src/dbt/kipptaf/models/exposures/cube.yml`, find the
`cube_semantic_layer.depends_on` list (it already contains
`- ref("fct_student_attendance_daily")` near line 73). Add immediately after the
`dim_student_enrollments` / attendance entries, in alphabetical position among
the `fct_*` entries:

```yaml
- ref("fct_student_enrollment_daily")
```

- [ ] **Step 3: Build the mart and its tests (dev target, deferred)**

Run:

```bash
uv run dbt build --select fct_student_enrollment_daily \
  --project-dir src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: the model builds to
`zz_<username>_kipptaf_marts.fct_student_enrollment_daily` and the `unique`,
`not_null`, `relationships`, and `dbt_utils.unique_combination_of_columns` tests
PASS. Note the row count printed (target ~18.9M; a dev defer build may be
smaller if upstreams are deferred to prod — that is fine, the relationships
still validate).

If a `relationships` test warns on a FK, it is likely stale-dev `--defer` drift
(see `src/dbt/CLAUDE.md` "Stale dev tables shadow `--defer`"). Re-run with the
parent dim in `--select` (e.g.
`--select fct_student_enrollment_daily dim_student_enrollments dim_students dim_locations dim_dates`)
before treating it as a real orphan.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster add src/dbt/kipptaf/models/marts/facts/properties/fct_student_enrollment_daily.yml src/dbt/kipptaf/models/exposures/cube.yml
git -C /workspaces/teamster commit -m "feat(dbt): fct_student_enrollment_daily properties, tests, exposure"
```

---

## Task 4: Singular tests for the anchor invariants

**Files:**

- Create:
  `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_latest_record_per_enrollment.sql`
- Create:
  `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_week_end_per_enrollment_week.sql`
- Create:
  `src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_month_end_per_enrollment_month.sql`
- Create:
  `src/dbt/kipptaf/tests/fct_student_enrollment_daily__no_null_entrydate_rows.sql`

Each singular test returns rows only on failure (the dbt convention). Project
`data_tests:` defaults supply `severity`/`store_failures`, so no `config()` is
needed (see `src/dbt/CLAUDE.md` "Test config defaults").

- [ ] **Step 1: Write the `is_latest_record` invariant test**

Create
`src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_latest_record_per_enrollment.sql`:

```sql
-- exactly one is_latest_record = true per student_enrollment_key
select student_enrollment_key, countif(is_latest_record) as n_latest,
from {{ ref("fct_student_enrollment_daily") }}
group by student_enrollment_key
having countif(is_latest_record) != 1
```

- [ ] **Step 2: Write the `is_week_end_record` invariant test**

Create
`src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_week_end_per_enrollment_week.sql`:

```sql
-- at most one is_week_end_record = 1 per (enrollment, ISO week)
select
    student_enrollment_key,
    -- trunk-ignore(sqlfluff/LT01): week(monday) special syntax
    date_trunc(date_key, week(monday)) as iso_week,
    sum(is_week_end_record) as n_week_end,
from {{ ref("fct_student_enrollment_daily") }}
group by
    student_enrollment_key,
    -- trunk-ignore(sqlfluff/LT01): week(monday) special syntax
    date_trunc(date_key, week(monday))
having sum(is_week_end_record) > 1
```

- [ ] **Step 3: Write the `is_month_end_record` invariant test**

Create
`src/dbt/kipptaf/tests/fct_student_enrollment_daily__one_month_end_per_enrollment_month.sql`:

```sql
-- at most one is_month_end_record = 1 per (enrollment, calendar month)
select
    student_enrollment_key,
    date_trunc(date_key, month) as cal_month,
    sum(is_month_end_record) as n_month_end,
from {{ ref("fct_student_enrollment_daily") }}
group by student_enrollment_key, date_trunc(date_key, month)
having sum(is_month_end_record) > 1
```

> **Note on `> 1` vs `!= 1`:** week/month-end use `> 1` (not `!= 1`) because the
> `current_date` cap can legitimately leave the in-progress week/month with its
> anchor day not-yet-occurred for a school whose latest in-session day precedes
> the period's true end — a stint may have zero week-end rows in its final
> partial week. `is_latest_record` uses `!= 1` because every stint always has
> exactly one last day. If Step 1's test fails with `n_latest = 2`, suspect
> intra-district transfer students (two stints, same academic_year) — that is
> expected and correct (two `student_enrollment_key` values), so the GROUP BY on
> `student_enrollment_key` already handles it; a real failure means a true
> partition bug.

- [ ] **Step 4: Write the null-entrydate exclusion test (Open item B gate)**

Create
`src/dbt/kipptaf/tests/fct_student_enrollment_daily__no_null_entrydate_rows.sql`:

```sql
-- the half-open join must drop all null-entrydate graduate placeholder stints;
-- their student_enrollment_key cannot appear in the fact
select sed.student_enrollment_key,
from {{ ref("fct_student_enrollment_daily") }} as sed
inner join
    {{ ref("dim_student_enrollments") }} as dse
    on sed.student_enrollment_key = dse.student_enrollment_key
where dse.entry_date_key is null
```

> **Implementer note:** confirm the null-entrydate column name on
> `dim_student_enrollments` is `entry_date_key` (it exposes `entry_date_key` per
> the cube YAML). If the dim stores the raw `entrydate` under a different name,
> adjust. Verify via `INFORMATION_SCHEMA.COLUMNS` on `dim_student_enrollments`
> before running.

- [ ] **Step 5: Run all four singular tests**

```bash
uv run dbt test --select fct_student_enrollment_daily \
  --project-dir src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: all tests (generic from Task 3 + the four singular) PASS. If
`one_latest_record` fails, inspect the failing keys — re-derive the
`row_number()` partition (`student_number, _dbt_source_project, academic_year`)
in the SQL.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster add src/dbt/kipptaf/tests/fct_student_enrollment_daily__*.sql
git -C /workspaces/teamster commit -m "test(dbt): anchor invariants for fct_student_enrollment_daily"
```

---

## Task 5: Rename the stint measure `count_students` → `count_enrollments`

**Files:**

- Modify: `src/cube/model/cubes/students/student_enrollments.yml:87-89`
- Modify: `src/cube/model/views/students/student_enrollments_summary.yml`
- Modify: `src/cube/model/views/students/student_enrollments_detail.yml`

The spec verified (2026-06-09) the blast radius is contained: the measure is
referenced only in its own cube and these two views — no Tableau extract or dbt
exposure consumes it by name.

- [ ] **Step 1: Confirm the blast radius is still contained**

```bash
rg -rn 'student_enrollments\.count_students|count_students' src/cube/model/cubes/students/student_enrollments.yml src/cube/model/views/students/student_enrollments_summary.yml src/cube/model/views/students/student_enrollments_detail.yml
rg -rln 'count_students' src/dbt/kipptaf/models/exposures/
```

Expected: matches only in the three files above; **no exposure** references it.
If a new consumer appeared since 2026-06-09, STOP and surface it to the user
before renaming.

- [ ] **Step 2: Rename the measure in the cube and add a description**

In `src/cube/model/cubes/students/student_enrollments.yml`, replace the
`measures:` block (lines 86-89):

```yaml
measures:
  - name: count_enrollments
    description: >-
      Count of enrollment records (stints), not a student headcount —
      count_distinct on student_enrollment_key. Alumni-inclusive and spans all
      academic years (a student with multiple stints counts once per stint; a
      graduate retains a placeholder stint per year). For a point-in-time
      student headcount use the student_enrollment_daily cube's count_students;
      for "students we served" use its count_students_served.
    sql: student_enrollment_key
    type: count_distinct
    public: true
```

- [ ] **Step 3: Rename + fix guidance in the summary view**

In `src/cube/model/views/students/student_enrollments_summary.yml`:

Change the `includes:` entry `- count_students` (line 14) to
`- count_enrollments`.

Replace the description's headcount guidance paragraph (the "Always use
count_students ... not student count." sentence) with:

```yaml
description: >-
  Aggregated student enrollment STINT counts and demographic breakdowns. No
  direct student identifiers — demographic dimensions (race, gender_identity,
  is_gifted) and status dimensions (ELL, IEP, meal) are aggregate breakdowns
  only.

  count_enrollments counts enrollment records (stints), NOT distinct students
  and NOT a point-in-time headcount: it is alumni-inclusive and spans all
  academic years. For a point-in-time student headcount (e.g. "enrollment on
  October 1" or "students enrolled in 2025") use the
  student_enrollment_daily_summary view's count_students; for "how many students
  we served this year" use its count_students_served.
```

- [ ] **Step 4: Rename + fix guidance in the detail view**

In `src/cube/model/views/students/student_enrollments_detail.yml`:

Change the `includes:` entry `- count_students` (line 15) to
`- count_enrollments`.

Replace the headcount sentence in the description ("Use count_students ... for
enrollment headcounts.") with:

```yaml
description: >-
  Student enrollment detail with enrollment-grain ELL, IEP, and meal eligibility
  status. One row per enrollment stint including graduate placeholder stints.

  count_enrollments (count_distinct on student_enrollment_key) counts enrollment
  records, not distinct students. Status fields (is_ell, is_iep,
  is_meal_eligible, etc.) reflect the enrollment-grain aggregate — not
  point-in-time within the stint. For point-in-time student headcounts use the
  student_enrollment_daily views.
```

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster add src/cube/model/cubes/students/student_enrollments.yml src/cube/model/views/students/student_enrollments_summary.yml src/cube/model/views/students/student_enrollments_detail.yml
git -C /workspaces/teamster commit -m "refactor(cube): rename student_enrollments.count_students to count_enrollments"
```

---

## Task 6: Create the `student_enrollment_daily` cube + wire `cube.js`

**Files:**

- Create: `src/cube/model/cubes/students/student_enrollment_daily.yml`
- Modify: `src/cube/cube.js`

- [ ] **Step 1: Write the cube YAML**

Create `src/cube/model/cubes/students/student_enrollment_daily.yml`. All
measures are `count_distinct(student_key)`; the three period anchors are int64
0/1 on the fact, declared `type: number` here and filtered `= 1`.
`is_latest_record` is boolean on the fact, declared `type: boolean` and filtered
`= true`.

```yaml
cubes:
  - name: student_enrollment_daily
    public: false
    sql_table: kipptaf_marts.fct_student_enrollment_daily

    joins:
      - name: dates
        sql: "{dates.date_day} = CAST({CUBE}.date_key AS TIMESTAMP)"
        relationship: many_to_one

      - name: students
        sql: "{students.student_key} = {CUBE}.student_key"
        relationship: many_to_one

      - name: locations
        sql: "{locations.location_key} = {CUBE}.location_key"
        relationship: many_to_one

      - name: student_enrollments
        sql: >
          {student_enrollments.student_enrollment_key} =
          {CUBE}.student_enrollment_key
        relationship: many_to_one

    dimensions:
      - name: student_enrollment_daily_key
        description: >-
          Surrogate key derived from student_number, _dbt_source_project, and
          date_key. Primary key for this fact.
        sql: student_enrollment_daily_key
        type: string
        primary_key: true

      - name: student_key
        description: Surrogate key derived from student_number. FK to students.
        sql: student_key
        type: string

      - name: student_enrollment_key
        description: >-
          FK to student_enrollments (the stint dimension). Surrogate key from
          student_number, _dbt_source_project, academic_year, entrydate.
        sql: student_enrollment_key
        type: string

      - name: location_key
        description: Surrogate key. FK to locations.
        sql: location_key
        type: string

      - name: enrollment_date
        description: The in-session school day this row represents.
        sql: CAST(date_key AS TIMESTAMP)
        type: time
        public: true

      - name: academic_year
        description: >-
          KIPP academic year (July start) of this day, from the school's
          year-record calendar term. 2025 = the 2025-26 school year.
        sql: academic_year
        type: number
        public: true

      - name: grade_level
        description: Grade level. 0 = Kindergarten, -2 = Preschool.
        sql: grade_level
        type: number
        public: true

      - name: enroll_status
        description: >-
          Enrollment status: 0 active, 2 withdrawn, 3 graduated. Student-level
          (current status), not point-in-time. Used only by
          count_students_active.
        sql: enroll_status
        type: number
        public: true

      - name: is_enrolled
        description:
          1 for every row (one enrolled in-session day). Row marker only.
        sql: is_enrolled
        type: number
        public: true

      - name: is_current_record
        description: >-
          1 on the school's last in-session day of the academic year that has
          actually occurred (capped at today). Per-school period-end-as-of-now
          marker — drives the default count_students at year / no grouping.
        # MUST be type: boolean with `= 1`, not type: number. The cube.js guard
        # injects `equals: [true]`, and BigQuery rejects `int64_col = TRUE`
        # ("No matching signature for operator =") — verified. Presenting the
        # int64 0/1 fact column as `is_current_record = 1` (BOOL) makes the
        # injected filter render `(is_current_record = 1) = TRUE`. Same for
        # is_month_end_record / is_week_end_record. (is_latest_record is already
        # a genuine boolean.) This matches how the attendance cube's anchor dims
        # are declared.
        sql: is_current_record = 1
        type: boolean
        public: true

      - name: is_month_end_record
        description: >-
          1 on the school's last in-session day of the calendar month that has
          occurred (capped at today). Use with timeDimensions granularity
          "month".
        sql: is_month_end_record
        type: number
        public: true

      - name: is_week_end_record
        description: >-
          1 on the school's last in-session day of the ISO week that has
          occurred (capped at today). Use with timeDimensions granularity
          "week".
        sql: is_week_end_record
        type: number
        public: true

      - name: is_latest_record
        description: >-
          TRUE on each student-stint's last enrolled in-session day of the
          academic year. Ever-enrolled marker (drives count_students_served) —
          NOT a period-end marker.
        sql: is_latest_record
        type: boolean
        public: true

    measures:
      - name: count_students
        description: >-
          Distinct students enrolled, point-in-time. Counts each student once as
          of the most recent in-session school day in your query: the exact date
          if you filter to one, otherwise each school's latest in-session day in
          the period (today for the current year, the last day of school for
          completed years). Matches the topline Total Enrollment methodology —
          enrollment is by entry/exit dates, not status. Note: when no single
          date is pinned, schools that end on different days are each counted as
          of their own last day, so a network total can mix as-of dates within
          the final weeks of a year. For 'how many students did we serve at any
          point' use count_students_served; for active-status roster use
          count_students_active.
        sql: student_key
        type: count_distinct
        public: true

      - name: count_students_served
        description: >-
          Distinct students enrolled at any point during the queried period. A
          student who enrolled and then withdrew mid-year is still counted. Use
          for 'how many students did we serve this year.' This is higher than
          count_students (point-in-time) by the number of mid-period
          enrollments/withdrawals. Not a point-in-time headcount — for that use
          count_students.
        sql: student_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.is_latest_record = true"

      - name: count_students_active
        description: >-
          Distinct students with an active enrollment status (excludes withdrawn
          and graduated). Use for current active-roster questions. WARNING:
          enrollment status is the student's current status, not their status on
          a past date — do not use this for historical point-in-time counts (use
          count_students with a date filter). Does not match topline Total
          Enrollment, which counts by enrollment dates rather than status.
        sql: student_key
        type: count_distinct
        public: true
        filters:
          - sql: "{CUBE}.enroll_status = 0"

      - name: count_students_oct01
        description: >-
          Distinct students enrolled on the October 1 state count date of the
          queried academic year. Point-in-time headcount for the regulatory fall
          enrollment count. Group by academic_year to compare count dates across
          years.
        sql: student_key
        type: count_distinct
        public: true
        filters:
          - sql: >-
              EXTRACT(MONTH FROM {CUBE}.date_key) = 10 AND EXTRACT(DAY FROM
              {CUBE}.date_key) = 1

      - name: count_students_oct15
        description: >-
          Distinct students enrolled on the October 15 state count date of the
          queried academic year. Point-in-time headcount for the regulatory fall
          enrollment count. Group by academic_year to compare count dates across
          years.
        sql: student_key
        type: count_distinct
        public: true
        filters:
          - sql: >-
              EXTRACT(MONTH FROM {CUBE}.date_key) = 10 AND EXTRACT(DAY FROM
              {CUBE}.date_key) = 15

      - name: count_students_mar15
        description: >-
          Distinct students enrolled on the March 15 state count date of the
          queried academic year. Point-in-time headcount for the regulatory
          spring enrollment count. Group by academic_year to compare count dates
          across years. (March 15 falls in the spring of the academic year —
          e.g. academic_year 2025 = March 15, 2026 — and is handled
          automatically.)
        sql: student_key
        type: count_distinct
        public: true
        filters:
          - sql: >-
              EXTRACT(MONTH FROM {CUBE}.date_key) = 3 AND EXTRACT(DAY FROM
              {CUBE}.date_key) = 15
```

> **Implementer note on `date_key` in measure filters:** The
> `count_students_oct01` etc. filters reference `{CUBE}.date_key`. The cube's
> time dimension is `enrollment_date` (a TIMESTAMP cast); the raw `date_key` is
> the DATE column on the fact. `EXTRACT(MONTH FROM {CUBE}.date_key)` reads the
> raw DATE column directly — valid because measure-filter SQL substitutes raw
> column references against the cube's `sql_table`. Do not route through
> `enrollment_date` (the TIMESTAMP cast) — `EXTRACT` on the DATE column is
> correct and cheaper.

- [ ] **Step 2: Wire `cube.js` — add the cube to the snapshot config**

In `src/cube/cube.js`, make four edits.

Edit A — add the cube to `SNAPSHOT_CUBES` (line 48):

```javascript
const SNAPSHOT_CUBES = ["student_attendance", "student_enrollment_daily"];
```

Edit B — add `count_students` stem to `SNAPSHOT_MEASURE_STEMS` (lines 56-61):

```javascript
const SNAPSHOT_MEASURE_STEMS = [
  "chronically_absent",
  "tier_1_2",
  "tier_3",
  "truant",
  "count_students",
];
```

Edit C — add `_served`, `_active`, **and the three count-date suffixes** to
`SNAPSHOT_SELF_ANCHORED_SUFFIXES` (lines 38-42). The count-date measures
(`count_students_oct01/oct15/mar15`) match the `count_students` stem via
`includes()`, so without their own suffix here the guard would inject
`is_current_record` on top of their date filter (→ "enrolled on Oct 1 AND on the
year-end day" → near-zero). They bake in their own date anchor, so they are
self-anchored and must be exempt:

```javascript
const SNAPSHOT_SELF_ANCHORED_SUFFIXES = [
  "_year_end",
  "_month_end",
  "_week_end",
  "_served",
  "_active",
  "_oct01",
  "_oct15",
  "_mar15",
];
```

Edit D — add the per-cube anchor override map immediately after the
`SNAPSHOT_ANCHOR_DIMENSIONS` definition (after line 37):

```javascript
// Per-cube override of the no-granularity default anchor. Enrollment's default
// is the per-school period-end-as-of-now flag (is_current_record), not the
// per-student-last-day flag (is_latest_record = "served"). Falls back to
// SNAPSHOT_ANCHOR_DIMENSIONS for any cube not listed here, so attendance's
// resolved anchor map is byte-for-byte unchanged.
const SNAPSHOT_ANCHOR_OVERRIDES = {
  student_enrollment_daily: { default: "is_current_record" },
};
```

- [ ] **Step 3: Wire `cube.js` — use the per-cube anchor map in the guard loop**

In `src/cube/cube.js`, inside the `for (const cubePrefix of SNAPSHOT_CUBES)`
loop, replace the anchor-selection logic. The current code (lines 251-285) reads
`SNAPSHOT_ANCHOR_DIMENSIONS` directly in two places — the anchor pick and the
`alreadyAnchored` check. Replace both with the per-cube `anchorMap`.

Find (around line 251-254):

```javascript
const anchorDimension =
  SNAPSHOT_ANCHOR_DIMENSIONS[granularity] ?? SNAPSHOT_ANCHOR_DIMENSIONS.default;
const anchorMember = `${cubePrefix}.${anchorDimension}`;
```

Replace with:

```javascript
const anchorMap = {
  ...SNAPSHOT_ANCHOR_DIMENSIONS,
  ...(SNAPSHOT_ANCHOR_OVERRIDES[cubePrefix] ?? {}),
};
const anchorDimension = anchorMap[granularity] ?? anchorMap.default;
const anchorMember = `${cubePrefix}.${anchorDimension}`;
```

Then find the `alreadyAnchored` first clause (around line 256-264):

```javascript
      const alreadyAnchored =
        filters.some(
          (f) =>
            Object.values(SNAPSHOT_ANCHOR_DIMENSIONS).some((d) =>
              f.member?.endsWith(d),
            ) &&
```

Replace `Object.values(SNAPSHOT_ANCHOR_DIMENSIONS)` with
`Object.values(anchorMap)`:

```javascript
      const alreadyAnchored =
        filters.some(
          (f) =>
            Object.values(anchorMap).some((d) => f.member?.endsWith(d)) &&
```

> **Implementer note:** `anchorMap` is declared with `const` inside the
> `for...of` loop body, so it is scoped per-iteration — no leakage between
> cubes. The `alreadyAnchored` use of `anchorMap` is in the same loop iteration,
> after the declaration, so it is in scope. Confirm by reading the final loop
> body top-to-bottom: `anchorMap` must be declared before both its uses.

- [ ] **Step 4: Verify the cube.js diff is scoped to anchor selection only**

```bash
git -C /workspaces/teamster diff src/cube/cube.js
```

Expected: changes touch only the four `const` arrays/maps at the top and the two
anchor-selection lines inside the loop. The access-control / location-scope path
of `queryRewrite` (the `networkGroup`/`regionGroup`/`schoolGroup` block and the
`isStudentMember` strip) must be **unchanged**. If the diff touches those,
revert and redo.

- [ ] **Step 5: Commit the cube + cube.js**

```bash
git -C /workspaces/teamster add src/cube/model/cubes/students/student_enrollment_daily.yml src/cube/cube.js
git -C /workspaces/teamster commit -m "feat(cube): student_enrollment_daily cube + snapshot anchor wiring"
```

---

## Task 7: Create the `student_enrollment_daily_summary` view

**Files:**

- Create: `src/cube/model/views/students/student_enrollment_daily_summary.yml`

Structural template:
`src/cube/model/views/student_attendance/student_attendance_summary.yml`. Single
`cube-access-student-data` policy (no PII tier — aggregate breakdowns only).

- [ ] **Step 1: Write the summary view YAML**

Create `src/cube/model/views/students/student_enrollment_daily_summary.yml`:

```yaml
views:
  - name: student_enrollment_daily_summary
    description: >-
      Point-in-time student enrollment headcounts and demographic breakdowns.
      One row per filter slice — never per student-day. No direct student
      identifiers; demographic dimensions are aggregate breakdowns only.

      Measure ladder (all count_distinct(student_key), all alumni-free because
      the year/date filter selects on the calendar day's school year, not
      student status):

      - count_students — point-in-time headcount. With a year filter, counts
        students enrolled as of each school's last occurred in-session day
        (period-end-as-of-now). With a single enrollment_date (e.g. 2025-10-01),
        counts students enrolled on that exact day. This is the default; it is
        governed by the snapshot guard so it is always a point-in-time snapshot,
        never an unanchored day-sum.
      - count_students_served — distinct students enrolled at any point in the
        period ("students we served"); includes mid-year leavers. The topline
        Total Enrollment analog.
      - count_students_active — active-status students only (status 0). Does NOT
        match topline by design; current-roster only, not historical
        point-in-time.
      - count_students_oct01 / _oct15 / _mar15 — point-in-time headcount on the
        state count dates; group by academic_year to compare across years.

      For point-in-time enrollment use count_students (or pin a single
      enrollment_date). Quarter granularity is unsupported — use month.

    cubes:
      - join_path: student_enrollment_daily
        includes:
          - count_students
          - count_students_served
          - count_students_active
          - count_students_oct01
          - count_students_oct15
          - count_students_mar15
          - grade_level
          - is_current_record
          - is_month_end_record
          - is_week_end_record
          - is_latest_record

      - join_path: student_enrollment_daily.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - quarter_number
          - academic_year

      - join_path: student_enrollment_daily.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_enrollment_daily.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_enrollment_daily.students
        prefix: false
        includes:
          - gender_identity
          - race
          - is_gifted

    meta:
      folders:
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_quarter_number
            - dates_academic_year
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state
        - name: Student
          members:
            - gender_identity
            - race
            - is_gifted
        - name: Enrollment
          members:
            - grade_level
        - name: Filter
          members:
            - is_current_record
            - is_month_end_record
            - is_week_end_record
            - is_latest_record

    access_policy:
      # No PII tier — view contains no direct student identifiers.
      # Demographic dimensions (race, gender_identity, is_gifted) are
      # aggregate breakdowns only.
      - group: cube-access-student-data
        member_level:
          includes: "*"
```

> **Implementer note on folder member names:** `prefix: true` joins produce
> `<last-join-segment>_<member>` (so `dates_date_day`, `regions_region_name`).
> `prefix: false` joins and top-cube members use the bare name (`grade_level`,
> `gender_identity`). Verify each folder member name matches the include it
> points at — a typo silently drops the member from the folder. Cube Cloud
> separates measures natively, so the six `count_students*` measures are NOT
> listed under `members:` (folders group dimensions only).

- [ ] **Step 2: Commit**

```bash
git -C /workspaces/teamster add src/cube/model/views/students/student_enrollment_daily_summary.yml
git -C /workspaces/teamster commit -m "feat(cube): student_enrollment_daily_summary view"
```

---

## Task 8: Create the `student_enrollment_daily_detail` view (PII-gated)

**Files:**

- Create: `src/cube/model/views/students/student_enrollment_daily_detail.yml`

Structural template:
`src/cube/model/views/students/student_enrollments_detail.yml`. Two-policy PII
access.

- [ ] **Step 1: Write the detail view YAML**

Create `src/cube/model/views/students/student_enrollment_daily_detail.yml`:

```yaml
views:
  - name: student_enrollment_daily_detail
    description: >-
      Row-level point-in-time student enrollment drill-down — one row per
      enrolled student-day. Use for roster exports and questions like "who was
      enrolled on October 1?". Same measures as the summary view plus the
      student-identifier members and the enrollment_date time dimension.

      count_students is point-in-time (as of the most recent in-session day in
      the query, or the pinned enrollment_date). count_students_served counts
      ever-enrolled in the period. count_students_active is active-status only
      (current-roster, not historical). Detail-view count_students for a fixed
      date equals the summary view's for the same filter.

    cubes:
      - join_path: student_enrollment_daily
        includes:
          - count_students
          - count_students_served
          - count_students_active
          - count_students_oct01
          - count_students_oct15
          - count_students_mar15
          - student_enrollment_daily_key
          - student_enrollment_key
          - grade_level
          - is_current_record
          - is_month_end_record
          - is_week_end_record
          - is_latest_record

      - join_path: student_enrollment_daily.dates
        prefix: true
        includes:
          - date_day
          - month_number
          - month_name
          - quarter_number
          - academic_year

      - join_path: student_enrollment_daily.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - grade_band
          - campus
          - city

      - join_path: student_enrollment_daily.locations.regions
        prefix: true
        includes:
          - region_name
          - state

      - join_path: student_enrollment_daily.students
        prefix: false
        includes:
          - student_key
          - full_name
          - birth_date
          - lea_student_identifier
          - state_student_identifier
          - gender_identity
          - race
          - is_gifted
          - enrollment_status

    meta:
      folders:
        - name: Enrollment
          members:
            - student_enrollment_daily_key
            - student_enrollment_key
            - grade_level
        - name: Date
          members:
            - dates_date_day
            - dates_month_number
            - dates_month_name
            - dates_quarter_number
            - dates_academic_year
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state
        - name: Student
          members:
            - student_key
            - full_name
            - birth_date
            - lea_student_identifier
            - state_student_identifier
            - gender_identity
            - race
            - is_gifted
            - enrollment_status
        - name: Filter
          members:
            - is_current_record
            - is_month_end_record
            - is_week_end_record
            - is_latest_record

    access_policy:
      - group: cube-access-student-data
        member_level:
          includes: "*"
          excludes:
            - full_name
            - birth_date
            - lea_student_identifier
            - state_student_identifier
            - district_student_identifier
            - salesforce_contact_id
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

> **Implementer note on the excludes list:** Copy the exclude list verbatim from
> `student_enrollments_detail.yml` (`full_name`, `birth_date`,
> `lea_student_identifier`, `state_student_identifier`,
> `district_student_identifier`, `salesforce_contact_id`). This view does not
> include `district_student_identifier` or `salesforce_contact_id` in its
> `includes`, but listing them in `excludes` is harmless and keeps the two
> detail views' policy blocks identical (Cube ignores an exclude for a member
> not present). Do NOT drop them — matching the sibling view is the convention.

- [ ] **Step 2: Commit**

```bash
git -C /workspaces/teamster add src/cube/model/views/students/student_enrollment_daily_detail.yml
git -C /workspaces/teamster commit -m "feat(cube): student_enrollment_daily_detail view (PII-gated)"
```

---

## Task 9: Validate in Cube Cloud Dev Mode + reconciliation acceptance gate

**Files:** none (validation + acceptance).

Cube has no local compile. This task validates the deployed model and runs the
spec's acceptance gate (Open item D). The cube reads
`kipptaf_marts.fct_student_enrollment_daily` — which exists in prod only after
merge. To test pre-merge, follow the `src/cube/CLAUDE.md` dev-schema procedure.

- [ ] **Step 1: Push the branch and open Cube Cloud Dev Mode**

```bash
git -C /workspaces/teamster push
```

Then in Cube Cloud → Data Model → Dev Mode → add this branch by name to spin up
a per-branch staging instance.

> **Pre-merge `sql_table` redirect (per `src/cube/CLAUDE.md`):** The fact does
> not exist in prod `kipptaf_marts` yet. To test the cube against your dev
> build: temporarily change `sql_table` in `student_enrollment_daily.yml` to
> `zz_<username>_kipptaf_marts.fct_student_enrollment_daily`, test, then REVERT
> before the final merge. Do not commit the `zz_` redirect (the security hook
> flags it). The build from Task 3 created that dev table.

- [ ] **Step 2: Confirm the cube compiles and the guard injects the right
      anchor**

In Dev Mode playground, compile (via `/sql`, not `/load`) a query on
`student_enrollment_daily_summary` with `count_students` and
`dates_academic_year = 2025`, no time grouping. Confirm the compiled SQL
contains an injected `is_current_record = 1` filter (the per-cube default
override). Then compile the same with `timeDimensions` granularity `month` —
confirm it injects `is_month_end_record = 1`.

Expected: year/no-grouping → `is_current_record`; month → `is_month_end_record`;
week → `is_week_end_record`. If it injects `is_latest_record`, the
`SNAPSHOT_ANCHOR_OVERRIDES` wiring (Task 6 Step 2-3) is wrong.

- [ ] **Step 3: Reconciliation gate — one-week topline match (Open item D)**

Query the dev fact directly (BigQuery MCP) for the week containing 2025-10-01,
filtered to that week's in-session days, by region, and compare to the spec's
verified targets:

```sql
select
  l.region_name,
  count(distinct f.student_key) as enrolled,
from `<schema>.fct_student_enrollment_daily` as f
inner join `<schema>.dim_locations` as l on f.location_key = l.location_key
where f.date_key between '2025-09-29' and '2025-10-03'
group by l.region_name
order by l.region_name
```

Expected (from the spec, verified 2026-06-09):

| Region   | Expected enrolled |
| -------- | ----------------- |
| Camden   | 2,161             |
| Miami    | 1,347             |
| Newark   | 6,611             |
| Paterson | 521               |
| Total    | 10,640            |

> **Note:** the spec's gate counts the topline `is_enrolled_week` population for
> the week. `count_students` over the week's days via
> `count(distinct student_key)` should match the 10,640 total. A small delta (±a
> few) may come from the week-boundary day set; if off by more than ~1%,
> investigate the half-open join boundary and the `insession = 1` filter before
> proceeding.

- [ ] **Step 4: Reconciliation gate — Oct 1 day-exact match**

```sql
select count(distinct student_key) as enrolled_oct01,
from `<schema>.fct_student_enrollment_daily`
where date_key = '2025-10-01'
```

Expected: ~10,637 (the spec's verified day-exact Oct 1 2025 count). Spot-check
against the upstream `is_enrolled_oct01` count for AY2025 (should be within a
handful — the upstream flag is stint-grain, the fact is day-grain).

- [ ] **Step 5: Default-grain spot checks**

```sql
-- AY2025 period-end-as-of-now (is_current_record): expect ~10,374
select count(distinct student_key)
from `<schema>.fct_student_enrollment_daily`
where academic_year = 2025 and is_current_record = 1;

-- AY2023 true year-end: expect ~9,630
select count(distinct student_key)
from `<schema>.fct_student_enrollment_daily`
where academic_year = 2023 and is_current_record = 1;

-- AY2025 served (is_latest_record): expect ~11,261
select count(distinct student_key)
from `<schema>.fct_student_enrollment_daily`
where academic_year = 2025 and is_latest_record;
```

Expected: matches the spec's verified figures (~10,374 / ~9,630 / ~11,261). A
material deviation means the anchor windows or the term-derived `academic_year`
are wrong — debug before merge.

- [ ] **Step 6: Detail-view PII gate check**

In Dev Mode, run `/load` on `student_enrollment_daily_detail` requesting
`full_name` under a `cube-access-student-data` (non-PII) context. Expected: 500
"You requested hidden member" (the gate works). Under `cube-access-student-pii`,
`full_name` resolves. Confirm detail-view `count_students` for `2025-10-01`
equals the summary view's for the same filter.

- [ ] **Step 7: Revert any `zz_` sql_table redirect**

If Step 1's note was applied, confirm `sql_table` in
`student_enrollment_daily.yml` is back to
`kipptaf_marts.fct_student_enrollment_daily`:

```bash
rg -n 'sql_table' src/cube/model/cubes/students/student_enrollment_daily.yml
```

Expected: `kipptaf_marts.fct_student_enrollment_daily` (no `zz_`).

---

## Task 10: Lint, final dbt build, and PR

**Files:** none new.

- [ ] **Step 1: Trunk-check the changed SQL/YAML before push**

From inside the worktree (or main repo root), check the changed files:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/marts/facts/fct_student_enrollment_daily.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_student_enrollment_daily.yml \
  src/dbt/kipptaf/tests/fct_student_enrollment_daily__*.sql \
  src/cube/model/cubes/students/student_enrollment_daily.yml \
  src/cube/model/views/students/student_enrollment_daily_summary.yml \
  src/cube/model/views/students/student_enrollment_daily_detail.yml \
  src/cube/cube.js
```

Expected: no findings. Fix any sqlfluff/yamllint/markdownlint issues (line
length ≤88, trailing commas, single quotes). Run from a path where `trunk` sees
your worktree edits (see root CLAUDE.md — relative paths from the main repo
check main-repo copies).

- [ ] **Step 2: Final full dbt build of the mart subtree**

```bash
uv run dbt build --select fct_student_enrollment_daily+ \
  --project-dir src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: mart + all its tests PASS. (The `+` includes nothing downstream in dbt
— Cube is not a dbt node — so this is the mart and its tests.)

- [ ] **Step 3: Push and open the PR**

```bash
git -C /workspaces/teamster push
```

Open the PR using `.github/pull_request_template.md` as the body. Reference the
issue: `Closes #4138`. Note in the PR body:

- The breaking rename `student_enrollments.count_students` → `count_enrollments`
  (blast radius contained to the cube + its two views; no exposure consumes it).
- The new mart is `materialized: table` (~18.9M rows).
- `cube.js` change is scoped to snapshot-anchor selection; attendance's resolved
  anchor map is unchanged (note the regression check from Step 4 below).
- Cube Cloud production redeploys on merge to `main` — no manual deploy step.

- [ ] **Step 4: After dbt Cloud CI passes, check warnings**

Per root CLAUDE.md: after CI passes, fetch warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`. Triage
marts-model warnings per the marts pre-merge checklist (search open issues by
model name + FK target before filing). Local-only relationships warnings absent
from CI are stale-dev `--defer` drift — ignore.

- [ ] **Step 5: Add a cube.js attendance-anchor regression note**

Per the spec ("Add a hooks/cube regression check that attendance's injected
anchors are unchanged"): in the PR, confirm via a Dev Mode `/sql` compile of an
**attendance** `count_chronically_absent` query (no grouping) that it still
injects `student_attendance.is_latest_record` (NOT `is_current_record`). This
proves the per-cube override did not leak into attendance. Document the check
result in the PR description.

---

## Self-Review (completed during planning)

**Spec coverage:**

- Component 1 (mart) → Tasks 2-4. ✓
- Component 2 (cube + cube.js) → Task 6. ✓ (all measures
  `count_distinct(student_key)`; `count_students` in `SNAPSHOT_MEASURE_STEMS`;
  `_served`/`_active` self-anchored; per-cube `is_current_record` default; named
  oct01/oct15/mar15 measures as date filters, no fact flags).
- Component 3 (summary view) → Task 7. ✓
- Component 4 (detail view, PII) → Task 8. ✓
- Measure rename (`count_students` → `count_enrollments`) → Task 5. ✓
- Exposure (`cube.yml depends_on`) → Task 3 Step 2. ✓
- Reconciliation gate (Open item D) → Task 9 Steps 3-5. ✓
- PII gate test → Task 9 Step 6. ✓
- `int_extracts__student_enrollments_weeks` untouched. ✓ (not referenced).

**Two spec/warehouse reconciliations** documented at top: terms `academic_year`
= `yearid + 1990`; `isyearrec = 1` is the deterministic single-term pick.

**Type consistency:** `student_enrollment_key` hash inputs
`[student_number, _dbt_source_project, academic_year, entrydate]` identical in
the SQL (Task 2), properties FK description (Task 3), and cube dimension
(Task 6) — matches `dim_student_enrollments` and `fct_student_attendance_daily`.
The three period anchors are `int64` on the fact and `type: number` in the cube
(filtered `= 1`); `is_latest_record` is `boolean` / `type: boolean` (filtered
`= true`) — consistent across Tasks 2, 3, 6.

**One open implementer decision flagged inline** (Task 2 Step 2): the exact
`schoolid → location_key` resolution model must be copied from
`dim_student_enrollments` rather than assumed — the plan instructs verifying it
against the warehouse before building.
