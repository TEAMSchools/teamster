# Topline Cascade Multi-Grain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the topline cascade dashboard extract at week, month,
academic-quarter, and YTD grains, config-driven per indicator, with the
aggregation materialized as a table (cost fix).

**Architecture:** A periods dimension (`int_topline__periods`) defines all
period windows. Period-scoped indicators (ADA, truancy, chronic absenteeism,
suspensions, contacts, i-Ready usage) get student × period variants computed
from date-bearing sources. Everything else is "as-of": the aggregated weekly
rows are relabeled into periods post-aggregation by picking each series' last
available week inside the period — no upstream changes. Goals resolve
most-specific-wins from a new long-format period-goals sheet tab, falling back
to the existing base goal.

**Tech Stack:** dbt (BigQuery), Google Sheets external sources, Tableau extract.

Spec: `docs/superpowers/specs/2026-07-09-topline-multigrain-design.md` (issue
[#4363](https://github.com/TEAMSchools/teamster/issues/4363)).

## Global Constraints

- Branch: `anthonygwalters/feat/claude-topline-multigrain` (exists, linked to
  #4363).
- All dbt commands: `uv run dbt ... --project-dir src/dbt/kipptaf` from repo
  root, target `dev`, with `--defer --state target/prod` (path relative to
  `--project-dir`).
- SQL conventions from `src/dbt/CLAUDE.md` apply: no `QUALIFY`, no `ORDER BY`,
  no subqueries against tables/CTEs, max 1 level of function nesting, ST06
  column ordering, trailing commas, 88-char lines.
- Staging tests set `config: severity: error`; staging models are
  contract-enforced and table-materialized by directory default.
- New/modified models need `description:` on the model and every column.
- Regression invariant: `period_type = 'week'` rows of the final extract must
  match current production output exactly (column adds excepted), EXCEPT the
  `region` column on staff-side rows: region normalization (Task 4b)
  intentionally changes `KIPP TEAM and Family Schools Inc.` → `TAF`,
  `KIPP Paterson` → `Paterson`, and staff region-level `aggregation_hash` /
  `aggregation_display` values shift with the sheet's entity rename. All other
  columns and all student-side rows match exactly.
- Region domain everywhere in the topline layer: `Newark` / `Camden` / `Miami` /
  `Paterson` / `TAF` (central-office staff) / `All` (org rows). The mapping
  lives in the `region_to_city` macro (Task 4b) — values match
  `dim_regions.name`; never join `dim_regions` from an intermediate.
- `period_rollup` blank/absent ⇒ `as_of`. Period goals only apply where the base
  config row has `has_goal = true`.
- Period labels are join keys with the sheet: months use full names (`October`),
  quarters `Q1`–`Q4` (reporting-terms `name`), weeks
  `format_date('%G-W%V', week_start_monday)`, YTD literal `YTD`.
- Commit after every task (conventional commits, `Refs #4363` in body).

## Documented deviations from the spec (flag in PR body)

1. **Chronic Absenteeism Interventions defaults to `as_of`, not `period`.** Its
   source is a snapshot (`snapshot_students__attendance_interventions_rollup`)
   holding cumulative counts — there is no event-grain data to recompute within
   a window. As-of is the only implementable semantics.
2. **i-Ready month boundaries are week-assigned, not exact.** The vendor source
   (`stg_iready__personalized_instruction_summary`) is pre-aggregated to weekly
   buckets; a bucket belongs to the month of its `date_range_start`. All other
   period-scoped indicators use exact daily or event dates.

---

### Task 1: Mock config seeds (DONE — committed on the branch)

The sheet tab and `period_rollup` column are deferred until stakeholders can
populate real data (Task 13). Two seeds stand in so the whole pipeline builds
and tests now:

- `src/dbt/kipptaf/seeds/seed_topline_period_rollup.csv` — one row per layer ×
  indicator (every pair on the current goals sheet, plus
  `Total Enrollment (Without SC OOD)`, `DIBELS PM Mastery`, and
  `Miami CRQ Mastery`, which have metric rows but no goal config) with the
  planned `as_of` / `period` assignments. Consumed DIRECTLY by Task 10's
  `rollup_config` CTE.
- `src/dbt/kipptaf/seeds/seed_topline_period_goals.csv` — mock period goals
  mirroring real config combinations (entities, school ids, grade bands all
  verified to hash-join against the normalized base sheet) with mock goal
  values. Rows deliberately exercise all four resolution-specificity branches
  plus a quarter ramp and a period goal on an as-of staff metric.
- `src/dbt/kipptaf/seeds/properties.yml` — column types, uniqueness,
  `accepted_values` tests. Both seeds are marked MOCK in their descriptions and
  are deleted at cutover (Task 13).

Already validated: `dbt seed` + 7 tests pass in dev; rollup seed covers every
sheet indicator pair with zero sheet-only gaps; every goals-seed row matches a
base config hash under the `region_to_city` normalization.

Nothing to execute here — proceed to Task 2.

---

### Task 2: Region macro + period-goals staging model (seed-backed)

**Files:**

- Create: `src/dbt/kipptaf/macros/region_to_city.sql`
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__topline_period_goals.sql`
- Create: entry in
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__topline_period_goals.yml`

The staging model reads `seed_topline_period_goals` for now; Task 13 swaps the
`from` clause to the sheet-tab source. Downstream models are agnostic.

**Interfaces:**

- Produces: model `stg_google_sheets__topline_period_goals` with columns
  `org_level string, entity string, schoolid int64, grade_low int64, grade_high int64, layer string, topline_indicator string, academic_year int64, period_type string, period_label string, goal numeric, aggregation_hash string`.
  Task 10 joins on (`layer`, `topline_indicator`, `aggregation_hash`,
  `period_type`) plus `period_label` / `academic_year` specificity.

- [ ] **Step 0: Create the region macro.** Maps long ADP business-unit names to
      city names; city names pass through unchanged (idempotent), so sheet
      inputs work in either form. Values intentionally match `dim_regions.name`
      — do NOT join `dim_regions` from intermediates (mart → intermediate layer
      inversion). Write `src/dbt/kipptaf/macros/region_to_city.sql`:

```sql
{% macro region_to_city(column_name) %}
    /* values match dim_regions.name — keep the two in sync */
    case
        {{ column_name }}
        when 'TEAM Academy Charter School'
        then 'Newark'
        when 'KIPP Cooper Norcross Academy'
        then 'Camden'
        when 'KIPP Miami'
        then 'Miami'
        when 'KIPP Paterson'
        then 'Paterson'
        when 'KIPP TEAM and Family Schools Inc.'
        then 'TAF'
        else {{ column_name }}
    end
{% endmacro %}
```

- [ ] **Step 2: Write the staging model.** Mirrors the base goals staging hash
      derivation (`stg_google_sheets__topline_aggregate_goals.sql:12-25`) but
      derives the hash from the CITY-normalized entity (cast-early — the
      normalized entity is a named column in the source CTE), and filters
      phantom rows. Reads the MOCK seed for now — the `-- TODO(#4363):` comment
      marks the Task 13 swap point:

```sql
with
    source as (
        select
            org_level,
            schoolid,
            grade_low,
            grade_high,
            layer,
            topline_indicator,
            academic_year,
            period_type,
            period_label,

            cast(goal as numeric) as goal,

            {{ region_to_city("entity") }} as entity,
        -- TODO(#4363): swap to the sheet-tab source at cutover (see plan
        -- Task 13) and delete the seed
        from {{ ref("seed_topline_period_goals") }}
        where topline_indicator is not null
    )

select
    org_level,
    schoolid,
    grade_low,
    grade_high,
    layer,
    topline_indicator,
    academic_year,
    period_type,
    period_label,
    goal,
    entity,

    case
        when layer = 'Outstanding Teammates' and org_level = 'org'
        then org_level
        when layer = 'Outstanding Teammates' and org_level = 'region'
        then entity
        when layer = 'Outstanding Teammates' and org_level = 'school'
        then cast(schoolid as string)
        when org_level = 'org'
        then 'org_' || grade_low || '-' || grade_high
        when org_level = 'region'
        then entity || '_' || grade_low || '-' || grade_high
        when org_level = 'school'
        then schoolid || '_' || grade_low || '-' || grade_high
    end as aggregation_hash,
from source
```

- [ ] **Step 3: Write the properties yml** (contract + uniqueness, staging
      severity error; composite key includes the nullable wildcard columns —
      BigQuery `group by` treats NULLs as equal, which is what we want):

```yaml
models:
  - name: stg_google_sheets__topline_period_goals
    description:
      Long-format period-specific goals for topline indicators, maintained by
      stakeholders on the topline goals spreadsheet. Each row overrides the base
      goal for one grain (period_type), optionally narrowed to a single period
      instance (period_label) and/or academic year. Blank period_label or
      academic_year acts as a wildcard. Resolution is most-specific-wins in
      int_topline__dashboard_aggregations.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - layer
              - topline_indicator
              - aggregation_hash
              - academic_year
              - period_type
              - period_label
          config:
            severity: error
    columns:
      - name: period_type
        description: Grain this goal applies to.
        data_type: string
        data_tests:
          - not_null:
              config:
                severity: error
          - accepted_values:
              arguments:
                values: [week, month, quarter, ytd]
              config:
                severity: error
      - name: goal
        description: Goal value, same units as the base goal column.
        data_type: numeric
        data_tests:
          - not_null:
              config:
                severity: error
      - name: org_level
        description:
          Aggregation level the goal row targets — org, region, or school.
        data_type: string
      - name: entity
        description: Region entity name, matching the aggregate goals tab.
        data_type: string
      - name: schoolid
        description:
          PowerSchool school id for school-level rows; null otherwise.
        data_type: int64
      - name: grade_low
        description:
          Low end of the grade band, matching the aggregate goals tab.
        data_type: int64
      - name: grade_high
        description:
          High end of the grade band, matching the aggregate goals tab.
        data_type: int64
      - name: layer
        description: Topline layer the indicator belongs to.
        data_type: string
      - name: topline_indicator
        description: Indicator name, matching the aggregate goals tab.
        data_type: string
      - name: academic_year
        description:
          Academic year (start year) the goal applies to; blank = every year.
        data_type: int64
      - name: period_label
        description:
          Period instance the goal applies to (full month name or Q1-Q4); blank
          = every instance of the grain.
        data_type: string
      - name: aggregation_hash
        description:
          Aggregation-grain hash derived identically to the aggregate goals
          staging model — joins period goals to their config row.
        data_type: string
```

- [ ] **Step 4: Build and test** (no sheet dependency — the seed is on the
      branch):

Run:

```bash
uv run dbt build \
  --select seed_topline_period_goals stg_google_sheets__topline_period_goals \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: seed loads, model builds, tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/google/sheets src/dbt/kipptaf/macros
git commit -m "feat(kipptaf): stage topline period goals from mock seed

Refs #4363"
```

---

### Task 3: `period_rollup` config (COLLAPSED — supplied by seed, no work)

`period_rollup` comes from `seed_topline_period_rollup` (Task 1), which Task
10's `rollup_config` CTE reads DIRECTLY — the seed's grain (one row per layer ×
indicator, uniqueness-tested) is exactly the config the aggregation needs, so
nothing flows through the base goals chain for now.

The sheet-column path (staging contract column, int passthrough with blank-safe
coalesce, rollup-consistency singular test) is specified in Task 13 for cutover.
Proceed to Task 4.

---

### Task 4: Periods dimension — `int_topline__periods`

**Files:**

- Create: `src/dbt/kipptaf/models/topline/intermediate/int_topline__periods.sql`
- Create:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__periods.yml`

**Interfaces:**

- Consumes: `int_powerschool__calendar_week` (kipptaf union; columns `schoolid`,
  `region`, `academic_year`, `week_start_monday`, `week_end_sunday`,
  `school_week_start_date`, `school_week_end_date`, `quarter`,
  `first_day_school_year`, `last_day_school_year`, `is_current_week_mon_sun`),
  `stg_google_sheets__reporting__terms` (type `RT` quarter dates per school).
- Produces: one row per scope × academic_year × period. Columns:
  `scope_key string` (school rows: `cast(schoolid as string)`; region rows:
  region name; org row: `'All'`), `org_scope string` (`school`/`region`/`org`),
  `region string`, `schoolid int64` (null on region/org rows),
  `academic_year int64`, `period_type string`, `period_label string`,
  `period_start date`, `period_end date`, `is_current_period boolean`,
  `is_most_recent_complete_period boolean`. Tasks 5–10 join on `scope_key` (or
  `schoolid` + `academic_year` for school-scope student variants) and window
  containment.

- [ ] **Step 1: Write the model.** School-scope periods are built from the
      calendar; region/org scopes derive as min/max of school windows per label
      (weeks are Mon–Sun aligned network-wide, months/quarters/ytd take the
      widest school window in scope):

```sql
with
    calendar_week as (
        select
            schoolid,
            region,
            academic_year,
            week_start_monday,
            week_end_sunday,
            school_week_start_date,
            school_week_end_date,
            first_day_school_year,
            last_day_school_year,
            `quarter`,

            format_date('%G-W%V', week_start_monday) as week_label,
        from {{ ref("int_powerschool__calendar_week") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    school_weeks as (
        select
            schoolid,
            region,
            academic_year,

            'week' as period_type,

            week_label as period_label,
            week_start_monday as period_start,
            week_end_sunday as period_end,
        from calendar_week
    ),

    school_months as (
        select
            schoolid,
            region,
            academic_year,

            'month' as period_type,

            format_date('%B', month_start) as period_label,
            month_start as period_start,
            last_day(month_start, month) as period_end,
        from calendar_week
        cross join
            unnest(
                generate_date_array(
                    date_trunc(first_day_school_year, month),
                    last_day_school_year,
                    interval 1 month
                )
            ) as month_start
        group by schoolid, region, academic_year, month_start
    ),

    school_quarters as (
        select
            rt.school_id as schoolid,
            rt.city as region,
            rt.academic_year,

            'quarter' as period_type,

            rt.name as period_label,
            rt.start_date as period_start,
            rt.end_date as period_end,
        from {{ ref("stg_google_sheets__reporting__terms") }} as rt
        where
            rt.type = 'RT'
            and rt.academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    school_ytd as (
        select
            schoolid,
            region,
            academic_year,

            'ytd' as period_type,
            'YTD' as period_label,

            min(school_week_start_date) as period_start,
            max(last_day_school_year) as period_end,
        from calendar_week
        group by schoolid, region, academic_year
    ),

    school_scope as (
        select *
        from school_weeks

        union all

        select *
        from school_months

        union all

        select *
        from school_quarters

        union all

        select *
        from school_ytd
    ),

    region_scope as (
        select
            cast(null as int) as schoolid,

            region,
            academic_year,
            period_type,
            period_label,

            min(period_start) as period_start,
            max(period_end) as period_end,
        from school_scope
        group by region, academic_year, period_type, period_label
    ),

    org_scope as (
        select
            cast(null as int) as schoolid,

            'All' as region,

            academic_year,
            period_type,
            period_label,

            min(period_start) as period_start,
            max(period_end) as period_end,
        from school_scope
        group by academic_year, period_type, period_label
    ),

    /* central-office staff normalize to region TAF (dim_regions.name) but
       have no school calendar — alias the network-wide org windows */
    taf_scope as (
        select
            cast(null as int) as schoolid,

            'TAF' as region,

            academic_year,
            period_type,
            period_label,

            min(period_start) as period_start,
            max(period_end) as period_end,
        from school_scope
        group by academic_year, period_type, period_label
    ),

    all_scopes as (
        select
            schoolid,
            region,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,

            'school' as org_scope,

            cast(schoolid as string) as scope_key,
        from school_scope

        union all

        select
            schoolid,
            region,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,

            'region' as org_scope,

            region as scope_key,
        from region_scope

        union all

        select
            schoolid,
            region,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,

            'region' as org_scope,

            region as scope_key,
        from taf_scope

        union all

        select
            schoolid,
            region,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,

            'org' as org_scope,

            region as scope_key,
        from org_scope
    ),

    flagged as (
        select
            *,

            if(
                current_date('{{ var("local_timezone") }}')
                between period_start and period_end,
                true,
                false
            ) as is_current_period,

            max(
                if(
                    period_end < current_date('{{ var("local_timezone") }}'),
                    period_end,
                    null
                )
            ) over (
                partition by org_scope, scope_key, academic_year, period_type
            ) as max_complete_period_end,
        from all_scopes
    )

select
    schoolid,
    region,
    academic_year,
    period_type,
    period_label,
    period_start,
    period_end,
    org_scope,
    scope_key,
    is_current_period,

    if(
        period_end < current_date('{{ var("local_timezone") }}')
        and period_end = max_complete_period_end
        and academic_year = {{ var("current_academic_year") }},
        true,
        false
    ) as is_most_recent_complete_period,
from flagged
```

- [ ] **Step 2: Write properties yml** — description per column, uniqueness
      test:

```yaml
models:
  - name: int_topline__periods
    description:
      Periods dimension for the topline cascade dashboard. One row per scope
      (school / region / org) x academic year x period, where periods are
      Mon-Sun weeks (from the PowerSchool calendar), exact calendar months
      clipped to the school year, reporting-term quarters (type RT), and one YTD
      row spanning the school year. Region and org scope windows are the min
      start / max end of the school windows sharing the label; a TAF region
      alias clones the network-wide org windows for central-office staff, who
      have no school calendar. Weeks are Mon-Sun aligned network-wide; school
      calendars diverge at year end, so consumers must pick each series' last
      available week inside a window rather than assuming the window's final
      week exists.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - org_scope
              - scope_key
              - academic_year
              - period_type
              - period_label
    columns:
      - name: schoolid
        description: PowerSchool school id; null on region and org scope rows.
        data_type: int64
      - name: region
        description: Region name; the literal All on org scope rows.
        data_type: string
      - name: academic_year
        description: Academic year (start year).
        data_type: int64
      - name: period_type
        description: Grain of the row — week, month, quarter, or ytd.
        data_type: string
      - name: period_label
        description:
          Display and join label — ISO week (2026-W14), full month name, Q1-Q4,
          or YTD.
        data_type: string
      - name: period_start
        description: First date of the period window.
        data_type: date
      - name: period_end
        description:
          Last date of the period window (calendar end, not clipped to today).
        data_type: date
      - name: org_scope
        description: Scope of the row — school, region, or org.
        data_type: string
      - name: scope_key
        description:
          Join key unifying scopes — schoolid as string for school rows, region
          name for region rows, All for the org rows.
        data_type: string
      - name: is_current_period
        description: True when today falls inside the period window.
        data_type: boolean
      - name: is_most_recent_complete_period
        description:
          True for the latest fully-elapsed period of its grain and scope in the
          current academic year.
        data_type: boolean
```

- [ ] **Step 3: Build and validate**

Run:

```bash
uv run dbt build --select int_topline__periods \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: PASS. Then sanity-check via BigQuery MCP against the dev schema: per
school × year expect ~40-44 week rows, 10-12 month rows, 4 quarter rows, 1 ytd
row; org scope has exactly one row per period_type × label × year.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/topline
git commit -m "feat(kipptaf): add topline periods dimension

Refs #4363"
```

---

### Task 4b: Region normalization — goals staging + staff-side intermediates

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__topline_aggregate_goals.sql`
- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__staff_metrics.sql`
- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__seats_staffed_weekly_aggregations.sql`
- Modify: matching properties ymls (new/changed column entries)

**Interfaces:**

- Consumes: `region_to_city` macro (Task 2 Step 0).
- Produces: `entity` on both goals staging models is city-normalized
  (`Newark`/`Camden`/`Miami`/`Paterson`/`TAF`) regardless of sheet form;
  `int_topline__staff_metrics.region` (new column, city-normalized);
  `int_topline__seats_staffed_weekly_aggregations.region` now city-normalized.
  Task 10's staff blocks join and group on `m.region`.

- [ ] **Step 1: Normalize the base goals staging model.** Restructure
      `stg_google_sheets__topline_aggregate_goals.sql` so entity is normalized
      in a source CTE and the hash/display derivations read the normalized value
      (output columns unchanged — contract untouched):

```sql
with
    source as (
        select
            * except (goal, entity),

            cast(goal as numeric) as goal,

            {{ region_to_city("entity") }} as entity,
        from
            {{
                source(
                    "google_sheets", "src_google_sheets__topline__aggregate_goals"
                )
            }}
    )

select
    *,

    if(
        grade_low = grade_high,
        cast(grade_high as string),
        if(grade_low = 0, 'K', cast(grade_low as string)) || '-' || grade_high
    ) as grade_band,

    case
        when layer = 'Outstanding Teammates' and org_level = 'org'
        then org_level
        when layer = 'Outstanding Teammates' and org_level = 'region'
        then entity
        when layer = 'Outstanding Teammates' and org_level = 'school'
        then cast(schoolid as string)
        when org_level = 'org'
        then 'org_' || grade_low || '-' || grade_high
        when org_level = 'region'
        then entity || '_' || grade_low || '-' || grade_high
        when org_level = 'school'
        then schoolid || '_' || grade_low || '-' || grade_high
    end as aggregation_hash,
from source
```

Update the `entity` column description in the staging yml: "Region entity,
normalized to city names (Newark / Camden / Miami / Paterson / TAF) via
region_to_city regardless of the sheet's form."

- [ ] **Step 2: Add normalized `region` to `int_topline__staff_metrics`.** In
      BOTH union branches: the macro renders a CASE expression, so per ST06
      ordering it belongs with the case statements near the bottom of each
      select (after `metric_value`), not beside the plain
      `ss.home_business_unit_name` ref:

```sql
    {{ region_to_city("ss.home_business_unit_name") }} as region,
```

Add the `region` column entry to the staff metrics properties yml (description:
"Region as city name, normalized from the ADP business unit — TAF for central
office."). Keep `home_business_unit_name` — downstream code switches to `region`
in Task 10 but the raw column remains for reference.

- [ ] **Step 3: Normalize `int_topline__seats_staffed_weekly_aggregations`.** In
      the `seat_tracker` CTE, replace the plain `entity` projection with the
      normalized value so every downstream join (including the internal goals
      joins on `entity`) and the output `region` column speak city names:

```sql
    seat_tracker as (
        select
            staffing_model_id,
            adp_location,
            valid_from,
            valid_to,
            is_staffed,

            {{ region_to_city("entity") }} as entity,
        from {{ ref("int_seat_tracker__snapshot") }}
        /* only active seats for the current academic year */
        where academic_year = {{ var("current_academic_year") }} and is_active
    ),
```

- [ ] **Step 4: Build and verify goal-join coverage is unchanged.**

```bash
uv run dbt build \
  --select stg_google_sheets__topline_aggregate_goals \
  int_google_sheets__topline_aggregate_goals int_topline__staff_metrics \
  int_topline__seats_staffed_weekly_aggregations \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: PASS. Then verify (BigQuery MCP) that the count of staff-side
aggregated rows with a matched goal config (`org_level is not null` in dev
`int_topline__dashboard_aggregations` — or, before Task 10 lands, count matched
rows joining dev `int_topline__staff_metrics.region` to dev goals `entity`)
equals the prod count of rows matched via `home_business_unit_name`. A drop
means an entity value fell through the macro — check for un-mapped business-unit
spellings.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models src/dbt/kipptaf/macros
git commit -m "feat(kipptaf): normalize topline regions to city names

Refs #4363"
```

---

### Task 5: Attendance period variant (ADA, Truancy, Chronic Absenteeism)

**Files:**

- Create:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__attendance_period.sql`
- Create:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__attendance_period.yml`

**Interfaces:**

- Consumes: `int_powerschool__ps_adaadm_daily_ctod` (daily; columns
  `student_number`, `studentid`, `schoolid`, `academic_year`, `calendardate`,
  `attendancevalue`, `membershipvalue`, `is_truant`), `int_topline__periods`
  (Task 4, school scope only).
- Produces: grain (`student_number`, `academic_year`, `schoolid`, `period_type`,
  `period_label`); columns additionally `period_start date`, `period_end date`,
  `attendance_value_sum float64`, `membership_value_sum float64`,
  `ada_period float64`, `is_truant_period_int int64`,
  `is_chronically_absent_period_int int64`. Task 9 consumes.

- [ ] **Step 1: Write the model.** Non-week periods only (week rows keep the
      existing weekly path). Date membership is exact (`calendardate` between
      window bounds):

```sql
with
    daily as (
        select
            student_number,
            schoolid,
            academic_year,
            calendardate,
            attendancevalue,
            membershipvalue,

            if(is_truant, 1, 0) as is_truant_int,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            attendancevalue is not null
            and calendardate >= '{{ var("current_academic_year") - 1 }}-07-01'
            and calendardate < current_date('{{ var("local_timezone") }}')
    ),

    periods as (
        select schoolid, academic_year, period_type, period_label,
            period_start, period_end,
        from {{ ref("int_topline__periods") }}
        where org_scope = 'school' and period_type != 'week'
    )

select
    d.student_number,
    d.academic_year,
    d.schoolid,

    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end,

    sum(d.attendancevalue) as attendance_value_sum,
    sum(d.membershipvalue) as membership_value_sum,
    max(d.is_truant_int) as is_truant_period_int,

    round(
        safe_divide(sum(d.attendancevalue), sum(d.membershipvalue)), 3
    ) as ada_period,

    if(
        safe_divide(sum(d.attendancevalue), sum(d.membershipvalue)) <= 0.90, 1, 0
    ) as is_chronically_absent_period_int,
from daily as d
inner join
    periods as p
    on d.schoolid = p.schoolid
    and d.academic_year = p.academic_year
    and d.calendardate between p.period_start and p.period_end
group by
    d.student_number,
    d.academic_year,
    d.schoolid,
    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end
```

- [ ] **Step 2: Properties yml** with descriptions and uniqueness on
      (`student_number`, `academic_year`, `schoolid`, `period_type`,
      `period_label`):

```yaml
models:
  - name: int_topline__attendance_period
    description:
      Student-level attendance metrics recomputed within exact non-week period
      windows (month / quarter / ytd) for the topline cascade dashboard. ADA is
      attendance over membership within the window; truancy is whether the
      student was flagged truant on any day in the window; chronic absenteeism
      is window ADA at or below 0.90.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - academic_year
              - schoolid
              - period_type
              - period_label
    columns:
      - name: student_number
        description: PowerSchool student number.
        data_type: int64
      - name: academic_year
        description: Academic year (start year).
        data_type: int64
      - name: schoolid
        description: PowerSchool school id.
        data_type: int64
      - name: period_type
        description: Grain of the row — month, quarter, or ytd.
        data_type: string
      - name: period_label
        description: Period instance label from the periods dimension.
        data_type: string
      - name: period_start
        description: First date of the period window.
        data_type: date
      - name: period_end
        description: Last date of the period window.
        data_type: date
      - name: attendance_value_sum
        description: Sum of attendance values on in-window days.
        data_type: float64
      - name: membership_value_sum
        description: Sum of membership values on in-window days.
        data_type: float64
      - name: ada_period
        description: Window ADA — attendance over membership, 3 decimals.
        data_type: float64
      - name: is_truant_period_int
        description: 1 when the student was truant on any day in the window.
        data_type: int64
      - name: is_chronically_absent_period_int
        description: 1 when window ADA is at or below 0.90.
        data_type: int64
```

- [ ] **Step 3: Build, test, reconcile**

Run:

```bash
uv run dbt build --select int_topline__attendance_period \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: PASS. Reconciliation (BigQuery MCP, dev schema): for a handful of
students, `ytd` rows' `ada_period` must equal the latest
`int_topline__ada_running_weekly.ada_running` (prod) for the same student — same
numerator/denominator definition, so exact match.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/topline
git commit -m "feat(kipptaf): add attendance period-grain topline variant

Refs #4363"
```

---

### Task 6: Suspension period variant

**Files:**

- Create:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__suspension_period.sql`
- Create:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__suspension_period.yml`

**Interfaces:**

- Consumes: `int_deanslist__incidents__penalties` (event grain; columns
  `student_school_id`, `create_ts_academic_year`, `school_id`, `start_date`,
  `incident_penalty_id`, `is_suspension`, `referral_tier`),
  `int_extracts__student_enrollments_weeks` (for the student→deanslist school
  mapping, mirroring `int_topline__suspension_weekly.sql:13-21`),
  `int_topline__periods`.
- Produces: grain (`student_number`, `academic_year`, `schoolid`, `period_type`,
  `period_label`) + `period_start`, `period_end`,
  `is_suspended_period_int int64`. Task 9 consumes.

- [ ] **Step 1: Write the model.** Mirror the weekly model's join hygiene
      (enrollment spine carries `deanslist_school_id`), but window by penalty
      `start_date` against the period. Use the deduplicated one-row-per-
      student-week spine only to resolve enrollment attributes — here we instead
      anchor on distinct student × school enrollment spans to avoid week
      fan-out:

```sql
with
    enrollments as (
        select distinct
            student_number,
            academic_year,
            schoolid,
            deanslist_school_id,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    periods as (
        select schoolid, academic_year, period_type, period_label,
            period_start, period_end,
        from {{ ref("int_topline__periods") }}
        where org_scope = 'school' and period_type != 'week'
    )

select
    e.student_number,
    e.academic_year,
    e.schoolid,

    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end,

    if(
        count(distinct if(ip.is_suspension, ip.incident_penalty_id, null)) > 0, 1, 0
    ) as is_suspended_period_int,
from enrollments as e
inner join
    periods as p
    on e.schoolid = p.schoolid
    and e.academic_year = p.academic_year
left join
    {{ ref("int_deanslist__incidents__penalties") }} as ip
    on e.student_number = ip.student_school_id
    and e.academic_year = ip.create_ts_academic_year
    and e.deanslist_school_id = ip.school_id
    and ip.start_date between p.period_start and p.period_end
    and ip.referral_tier not in ('Non-Behavioral', 'Social Work')
group by
    e.student_number,
    e.academic_year,
    e.schoolid,
    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end
```

- [ ] **Step 2: Properties yml** — same key/uniqueness pattern as Task 5
      (columns: the five key columns plus `period_start`, `period_end`,
      `is_suspended_period_int`; model description "1 when the student received
      any qualifying suspension penalty starting within the period window;
      mirrors the weekly running suspension definition scoped to the window").
      Copy the Task 5 yml structure, adjust names/descriptions.

```yaml
models:
  - name: int_topline__suspension_period
    description:
      Student-level suspension flag recomputed within exact non-week period
      windows for the topline cascade dashboard. 1 when the student received any
      qualifying suspension penalty (is_suspension, non-behavioral and
      social-work referral tiers excluded) with a start date inside the window.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - academic_year
              - schoolid
              - period_type
              - period_label
    columns:
      - name: student_number
        description: PowerSchool student number.
        data_type: int64
      - name: academic_year
        description: Academic year (start year).
        data_type: int64
      - name: schoolid
        description: PowerSchool school id.
        data_type: int64
      - name: period_type
        description: Grain of the row — month, quarter, or ytd.
        data_type: string
      - name: period_label
        description: Period instance label from the periods dimension.
        data_type: string
      - name: period_start
        description: First date of the period window.
        data_type: date
      - name: period_end
        description: Last date of the period window.
        data_type: date
      - name: is_suspended_period_int
        description:
          1 when any qualifying suspension penalty started inside the window.
        data_type: int64
```

- [ ] **Step 3: Build and reconcile**

```bash
uv run dbt build --select int_topline__suspension_period \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: PASS. Reconcile: `ytd` rows' school-level average must match the
latest weekly `is_suspended_y1_all_running` school average from prod for the
same school (spot-check 2-3 schools).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/topline
git commit -m "feat(kipptaf): add suspension period-grain topline variant

Refs #4363"
```

---

### Task 7: Attendance-contacts period variant

**Files:**

- Create:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__attendance_contacts_period.sql`
- Create:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__attendance_contacts_period.yml`

**Interfaces:**

- Consumes: `int_topline__attendance_contacts` (one row per absence day ×
  student; columns `student_number`, `academic_year`, `schoolid`,
  `calendardate`, `is_successful_int`, `is_enrolled_week`),
  `int_topline__periods`.
- Produces: grain (`student_number`, `academic_year`, `schoolid`, `period_type`,
  `period_label`) + `period_start`, `period_end`, `successful_comms_sum int64`,
  `required_comms_count int64`. Task 9 consumes.

- [ ] **Step 1: Write the model** (exact date membership on the absence day):

```sql
with
    contacts as (
        select
            student_number,
            academic_year,
            schoolid,
            calendardate,
            is_successful_int,
        from {{ ref("int_topline__attendance_contacts") }}
        where
            is_enrolled_week
            and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    periods as (
        select schoolid, academic_year, period_type, period_label,
            period_start, period_end,
        from {{ ref("int_topline__periods") }}
        where org_scope = 'school' and period_type != 'week'
    )

select
    c.student_number,
    c.academic_year,
    c.schoolid,

    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end,

    sum(c.is_successful_int) as successful_comms_sum,
    count(c.is_successful_int) as required_comms_count,
from contacts as c
inner join
    periods as p
    on c.schoolid = p.schoolid
    and c.academic_year = p.academic_year
    and c.calendardate between p.period_start and p.period_end
group by
    c.student_number,
    c.academic_year,
    c.schoolid,
    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end
```

- [ ] **Step 2: Properties yml:**

```yaml
models:
  - name: int_topline__attendance_contacts_period
    description:
      Successful attendance-contact rate inputs recomputed within exact non-week
      period windows for the topline cascade dashboard. Numerator is successful
      contacts on absence days inside the window; denominator is required
      contacts (absence days) inside the window.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - academic_year
              - schoolid
              - period_type
              - period_label
    columns:
      - name: student_number
        description: PowerSchool student number.
        data_type: int64
      - name: academic_year
        description: Academic year (start year).
        data_type: int64
      - name: schoolid
        description: PowerSchool school id.
        data_type: int64
      - name: period_type
        description: Grain of the row — month, quarter, or ytd.
        data_type: string
      - name: period_label
        description: Period instance label from the periods dimension.
        data_type: string
      - name: period_start
        description: First date of the period window.
        data_type: date
      - name: period_end
        description: Last date of the period window.
        data_type: date
      - name: successful_comms_sum
        description: Successful attendance contacts on in-window absence days.
        data_type: int64
      - name: required_comms_count
        description: Required attendance contacts (absence days) in the window.
        data_type: int64
```

- [ ] **Step 3: Build and reconcile**

```bash
uv run dbt build --select int_topline__attendance_contacts_period \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: PASS. Reconcile `ytd` sums vs. the latest weekly
`successful_comms_sum_running` / `required_comms_count_running` (prod) for
sampled students.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/topline
git commit -m "feat(kipptaf): add attendance contacts period-grain variant

Refs #4363"
```

---

### Task 8: i-Ready lessons period variant

**Files:**

- Create:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__iready_lessons_period.sql`
- Create:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__iready_lessons_period.yml`

**Interfaces:**

- Consumes: `int_topline__iready_lessons_weekly` (student × week × discipline;
  `n_lessons_passed_week`, `time_on_task_min_week`, `week_start_monday`),
  `int_extracts__student_enrollments_subjects_weeks` (already joined upstream —
  reuse the weekly model, do NOT re-derive), `int_topline__periods`.
- Produces: grain (`student_number`, `academic_year`, `schoolid`, `discipline`,
  `period_type`, `period_label`) + `period_start`, `period_end`,
  `week_count int64`, `lessons_passed_sum int64`,
  `time_on_task_min_sum float64`, `meets_lessons_passed_period_int int64` (avg ≥
  2 lessons/week), `time_on_task_min_week_avg float64`. Task 9 consumes.

- [ ] **Step 1: Write the model.** DEVIATION (documented above): iReady buckets
      are weekly; a bucket belongs to the month of its `week_start_monday`.
      `schoolid` comes from the weekly model's spine — confirm
      `int_topline__iready_lessons_weekly` exposes it; it currently does NOT
      (only `student_number`, `academic_year`, weeks, `discipline`, metrics).
      First add `co.schoolid,` to `int_topline__iready_lessons_weekly.sql`'s
      select (spine column passthrough, backwards-compatible), then:

```sql
with
    weekly as (
        select
            student_number,
            academic_year,
            schoolid,
            discipline,
            week_start_monday,

            coalesce(n_lessons_passed_week, 0) as n_lessons_passed_week,
            coalesce(time_on_task_min_week, 0) as time_on_task_min_week,
        from {{ ref("int_topline__iready_lessons_weekly") }}
    ),

    periods as (
        select schoolid, academic_year, period_type, period_label,
            period_start, period_end,
        from {{ ref("int_topline__periods") }}
        where org_scope = 'school' and period_type != 'week'
    )

select
    w.student_number,
    w.academic_year,
    w.schoolid,
    w.discipline,

    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end,

    count(*) as week_count,
    sum(w.n_lessons_passed_week) as lessons_passed_sum,
    sum(w.time_on_task_min_week) as time_on_task_min_sum,

    round(
        safe_divide(sum(w.time_on_task_min_week), count(*)), 1
    ) as time_on_task_min_week_avg,

    if(
        safe_divide(sum(w.n_lessons_passed_week), count(*)) >= 2, 1, 0
    ) as meets_lessons_passed_period_int,
from weekly as w
inner join
    periods as p
    on w.schoolid = p.schoolid
    and w.academic_year = p.academic_year
    and w.week_start_monday between p.period_start and p.period_end
group by
    w.student_number,
    w.academic_year,
    w.schoolid,
    w.discipline,
    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end
```

- [ ] **Step 2: Properties yml.** Also add the new `schoolid` column entry
      (description "PowerSchool school id from the enrollment spine.", data_type
      int64) to `int_topline__iready_lessons_weekly.yml`:

```yaml
models:
  - name: int_topline__iready_lessons_period
    description:
      Student-level i-Ready usage metrics aggregated over non-week period
      windows for the topline cascade dashboard. The vendor source is
      pre-aggregated to weekly buckets, so a bucket belongs to the month of its
      week start (week-assigned month boundaries, not exact). Metrics are
      per-enrolled-week averages so weekly goals stay comparable across grains.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - academic_year
              - schoolid
              - discipline
              - period_type
              - period_label
    columns:
      - name: student_number
        description: PowerSchool student number.
        data_type: int64
      - name: academic_year
        description: Academic year (start year).
        data_type: int64
      - name: schoolid
        description: PowerSchool school id.
        data_type: int64
      - name: discipline
        description: Subject area — ELA or Math.
        data_type: string
      - name: period_type
        description: Grain of the row — month, quarter, or ytd.
        data_type: string
      - name: period_label
        description: Period instance label from the periods dimension.
        data_type: string
      - name: period_start
        description: First date of the period window.
        data_type: date
      - name: period_end
        description: Last date of the period window.
        data_type: date
      - name: week_count
        description: Enrolled weeks with an i-Ready row inside the window.
        data_type: int64
      - name: lessons_passed_sum
        description: Lessons passed across in-window weeks.
        data_type: int64
      - name: time_on_task_min_sum
        description: Time on task minutes across in-window weeks.
        data_type: float64
      - name: time_on_task_min_week_avg
        description: Average time on task minutes per in-window week.
        data_type: float64
      - name: meets_lessons_passed_period_int
        description:
          1 when the student averaged at least 2 lessons passed per in-window
          week.
        data_type: int64
```

- [ ] **Step 3: Build both models and test**

```bash
uv run dbt build \
  --select int_topline__iready_lessons_weekly int_topline__iready_lessons_period \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/topline
git commit -m "feat(kipptaf): add iready lessons period-grain topline variant

Refs #4363"
```

---

### Task 9: Period-grain student metric union — `int_topline__student_metrics_periods`

**Files:**

- Create:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__student_metrics_periods.sql`
- Create:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__student_metrics_periods.yml`

**Interfaces:**

- Consumes: Tasks 5–8 variants; `int_extracts__student_enrollments_weeks`
  (student attributes: `region`, `school`, `grade_level`, `week_start_monday`,
  `is_enrolled_week`).
- Produces: same shape as `int_topline__student_metrics` plus period columns —
  (`student_number`, `academic_year`, `region`, `schoolid`, `school`,
  `grade_level`, `layer`, `indicator`, `discipline`, `term date` (=
  period_start), `term_end date` (= period_end), `period_type`, `period_label`,
  `numerator`, `denominator`, `metric_value`). Task 10 unions it into the
  aggregation input.

- [ ] **Step 1: Write the model.** Student attributes come from the last
      enrolled week inside the window (window max + `where`, no `qualify`):

```sql
with
    metric_union as (
        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Attendance and Enrollment' as layer,
            'ADA' as indicator,
            cast(null as string) as discipline,

            attendance_value_sum as numerator,
            membership_value_sum as denominator,
            ada_period as metric_value,
        from {{ ref("int_topline__attendance_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Attendance and Enrollment' as layer,
            'Truancy' as indicator,
            cast(null as string) as discipline,

            null as numerator,
            null as denominator,

            is_truant_period_int as metric_value,
        from {{ ref("int_topline__attendance_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Attendance and Enrollment' as layer,
            'Chronic Absenteeism' as indicator,
            cast(null as string) as discipline,

            null as numerator,
            null as denominator,

            is_chronically_absent_period_int as metric_value,
        from {{ ref("int_topline__attendance_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Attendance and Enrollment' as layer,
            'Successful Contacts' as indicator,
            cast(null as string) as discipline,

            successful_comms_sum as numerator,
            required_comms_count as denominator,

            safe_divide(successful_comms_sum, required_comms_count) as metric_value,
        from {{ ref("int_topline__attendance_contacts_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'Student and Family Experience' as layer,
            'Suspensions' as indicator,
            cast(null as string) as discipline,

            null as numerator,
            null as denominator,

            is_suspended_period_int as metric_value,
        from {{ ref("int_topline__suspension_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'K-8 Reading and Math' as layer,
            'i-Ready Lessons Passed' as indicator,
            discipline,

            null as numerator,
            null as denominator,

            meets_lessons_passed_period_int as metric_value,
        from {{ ref("int_topline__iready_lessons_period") }}

        union all

        select
            student_number,
            academic_year,
            schoolid,
            period_type,
            period_label,
            period_start,
            period_end,

            'K-8 Reading and Math' as layer,
            'i-Ready Time on Task' as indicator,
            discipline,

            null as numerator,
            null as denominator,

            time_on_task_min_week_avg as metric_value,
        from {{ ref("int_topline__iready_lessons_period") }}
    ),

    enrolled_weeks as (
        select
            student_number,
            academic_year,
            schoolid,
            region,
            school,
            grade_level,
            week_start_monday,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where
            is_enrolled_week
            and academic_year >= {{ var("current_academic_year") - 1 }}
            and region != 'Paterson'
    ),

    attrs_ranked as (
        select
            mu.*,

            ew.region,
            ew.school,
            ew.grade_level,

            max(ew.week_start_monday) over (
                partition by
                    mu.student_number,
                    mu.academic_year,
                    mu.schoolid,
                    mu.layer,
                    mu.indicator,
                    mu.discipline,
                    mu.period_type,
                    mu.period_label
            ) as max_week_in_period,

            ew.week_start_monday as attr_week,
        from metric_union as mu
        inner join
            enrolled_weeks as ew
            on mu.student_number = ew.student_number
            and mu.academic_year = ew.academic_year
            and mu.schoolid = ew.schoolid
            and ew.week_start_monday between mu.period_start and mu.period_end
    )

select
    student_number,
    academic_year,
    region,
    schoolid,
    school,
    grade_level,
    layer,
    indicator,
    discipline,
    period_type,
    period_label,
    numerator,
    denominator,
    metric_value,

    period_start as term,
    period_end as term_end,
from attrs_ranked
where attr_week = max_week_in_period
```

- [ ] **Step 2: Properties yml:**

```yaml
models:
  - name: int_topline__student_metrics_periods
    description:
      Period-scoped student metric rows (month / quarter / ytd) for the topline
      cascade dashboard, unioning the period-grain indicator variants into the
      same shape as int_topline__student_metrics. Student attributes (region,
      school, grade level) come from the student's last enrolled week inside the
      window; the inner join to enrolled weeks also applies the Paterson
      exclusion and enrollment gate matching the weekly path. Week rows are NOT
      produced here — they stay on the weekly path.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - academic_year
              - schoolid
              - layer
              - indicator
              - discipline
              - period_type
              - period_label
    columns:
      - name: student_number
        description: PowerSchool student number.
        data_type: int64
      - name: academic_year
        description: Academic year (start year).
        data_type: int64
      - name: region
        description: Region name from the last enrolled in-window week.
        data_type: string
      - name: schoolid
        description: PowerSchool school id.
        data_type: int64
      - name: school
        description: School name from the last enrolled in-window week.
        data_type: string
      - name: grade_level
        description: Grade level from the last enrolled in-window week.
        data_type: int64
      - name: layer
        description: Topline layer the indicator belongs to.
        data_type: string
      - name: indicator
        description: Topline indicator name.
        data_type: string
      - name: discipline
        description: Subject area where applicable; null otherwise.
        data_type: string
      - name: period_type
        description: Grain of the row — month, quarter, or ytd.
        data_type: string
      - name: period_label
        description: Period instance label from the periods dimension.
        data_type: string
      - name: numerator
        description: Rate numerator for Divide-aggregated indicators.
        data_type: float64
      - name: denominator
        description: Rate denominator for Divide-aggregated indicators.
        data_type: float64
      - name: metric_value
        description: Student-level metric value for the period.
        data_type: float64
      - name: term
        description: Period start date (mirrors the weekly column name).
        data_type: date
      - name: term_end
        description: Period end date (mirrors the weekly column name).
        data_type: date
```

- [ ] **Step 3: Build and test**

```bash
uv run dbt build --select int_topline__student_metrics_periods \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/topline
git commit -m "feat(kipptaf): union period-grain topline student metrics

Refs #4363"
```

---

### Task 10: Rewrite `int_topline__dashboard_aggregations`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__dashboard_aggregations.sql`
  (full rewrite)
- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__dashboard_aggregations.yml`
  (materialization, tests, contract-free but full column docs)

**Interfaces:**

- Consumes: everything above plus the existing weekly inputs
  (`int_topline__student_metrics`, `int_topline__staff_metrics`,
  `int_topline__student_retention_weekly_aggregations`,
  `int_topline__seats_staffed_weekly_aggregations`,
  `stg_google_sheets__topline_enrollment_targets`).
- Produces: today's column set PLUS `period_type string`, `period_label string`,
  `is_current_period boolean`, `is_most_recent_complete_period boolean`.
  `term`/`term_end` hold period bounds. `is_current_week` is preserved and now
  carries the row's period-currency (identical values on week rows). Task 11
  consumes.

Structure of the rewrite (the full file follows this exact CTE order):

1. `student_metrics` — existing weekly student rows with `'week' as period_type`
   and `format_date('%G-W%V', term) as period_label`.
2. `student_metrics_periods` — passthrough of Task 9's model.
3. `student_metrics_all` — union of 1 and 2. Task 9 rows have no
   `is_current_week` — select `cast(null as boolean) as is_current_week` in that
   branch; the final select outputs
   `coalesce(is_current_week, is_current_period) as is_current_week` so the
   legacy column carries period-currency on non-week rows.
4. `pre_agg_union_student` — the existing three org-level GROUP BY blocks
   (preserve verbatim from the current file), with `period_type`, `period_label`
   added to every select list and every `group by`.
5. `agg_union_staff` — existing staff blocks (weekly only), same two period
   columns added (`'week'`, ISO label from `week_start_monday`), and switched to
   the normalized region: select/group `m.region` (Task 4b column) instead of
   `m.home_business_unit_name`, and join goals on `m.region = g.entity` (both
   sides city-normalized after Task 4b). The seats-staffed passthrough block
   needs only the period columns — its `region` is already normalized.
6. `retention` — passthrough of the retention weekly aggregations with the two
   week period columns.
7. `agg_week_and_period` — one union of all aggregated rows with `metric_type`
   assigned per branch (retention → `'Student Metrics'`, seats staffed →
   `'Staff Metrics'`, matching today's final union membership). All branches
   emit city-normalized `region` (`Newark` / `Camden` / `Miami` / `Paterson` /
   `TAF` / `All`) — the periods dimension speaks the same domain, so no decode
   layer is needed here.
8. Novel CTEs — complete SQL below: `keyed`, `rollup_config`,
   `as_of_candidates`, `as_of_rows`, `all_rows`, then targets and goal
   resolution, then the single final select with the existing goal math and
   `where term <= current_date('{{ var("local_timezone") }}')` (period rows:
   `term` = period_start, so future periods drop out).

Complete SQL for the novel CTEs (column lists abbreviated to the
mechanism-relevant ones — carry ALL existing metric and goal-config columns
through every CTE):

```sql
    keyed as (
        select
            *,

            coalesce(cast(schoolid as string), region) as scope_key,
        from agg_week_and_period
    ),

    rollup_config as (
        /* TODO(#4363): repoint to int_google_sheets__topline_aggregate_goals
           .period_rollup at sheet cutover (plan Task 13) */
        select layer, topline_indicator, period_rollup,
        from {{ ref("seed_topline_period_rollup") }}
    ),

    flags as (
        select
            k.*,

            p.is_current_period,
            p.is_most_recent_complete_period,
        from keyed as k
        left join
            {{ ref("int_topline__periods") }} as p
            on k.scope_key = p.scope_key
            and k.academic_year = p.academic_year
            and k.period_type = p.period_type
            and k.period_label = p.period_label
    ),

    as_of_candidates as (
        select
            f.*,

            p.period_type as p_period_type,
            p.period_label as p_period_label,
            p.period_start as p_period_start,
            p.period_end as p_period_end,
            p.is_current_period as p_is_current_period,
            p.is_most_recent_complete_period as p_is_most_recent_complete_period,

            max(f.term) over (
                partition by
                    f.metric_type,
                    f.academic_year,
                    f.scope_key,
                    f.region,
                    f.schoolid,
                    f.school,
                    f.layer,
                    f.indicator,
                    f.discipline,
                    f.aggregation_hash,
                    p.period_type,
                    p.period_label
            ) as max_term_in_period,
        from flags as f
        inner join
            {{ ref("int_topline__periods") }} as p
            on f.scope_key = p.scope_key
            and f.academic_year = p.academic_year
            and f.term between p.period_start and p.period_end
            and p.period_type != 'week'
        left join
            rollup_config as rc
            on f.layer = rc.layer
            and f.indicator = rc.topline_indicator
        where
            f.period_type = 'week'
            and (rc.period_rollup = 'as_of' or rc.period_rollup is null)
    ),

    as_of_rows as (
        select
            * except (
                term,
                term_end,
                period_type,
                period_label,
                is_current_period,
                is_most_recent_complete_period,
                p_period_type,
                p_period_label,
                p_period_start,
                p_period_end,
                p_is_current_period,
                p_is_most_recent_complete_period,
                max_term_in_period
            ),

            p_period_start as term,
            p_period_end as term_end,
            p_period_type as period_type,
            p_period_label as period_label,
            p_is_current_period as is_current_period,
            p_is_most_recent_complete_period as is_most_recent_complete_period,
        from as_of_candidates
        where term = max_term_in_period
    ),

    all_rows as (
        select <canonical column list>
        from flags

        union all

        select <canonical column list>
        from as_of_rows
    ),
```

Where `<canonical column list>` appears, enumerate exactly these columns (the
model's working set — the internal helper `scope_key` is carried through to the
final select, which drops it):

```text
metric_type, academic_year, region, scope_key, schoolid,
school, layer, indicator, discipline, term, term_end, is_current_week,
period_type, period_label, is_current_period,
is_most_recent_complete_period, indicator_display, org_level, has_goal,
goal_type, goal_direction, aggregation_data_type, aggregation_type,
aggregation_hash, aggregation_display, goal, metric_aggregate_value
```

The targets chain then reads `all_rows` (not `pre_agg_union_student`):
`enrollment` filters `indicator = 'Total Enrollment (Without SC OOD)'` and keeps
`period_type`/`period_label`/flag columns through `targets`, `target_unpivot`
(add the four period/flag columns to the unpivot select list), and
`target_goals` — otherwise identical to the current file. Then:

```sql
    with_target_rows as (
        select <canonical column list>
        from all_rows

        union all

        select <canonical column list>
        from target_goals
    ),

    resolved_goals as (
        select
            r.*,

            coalesce(pg1.goal, pg2.goal, pg3.goal, pg4.goal, r.goal) as goal_resolved,
        from with_target_rows as r
        left join
            {{ ref("stg_google_sheets__topline_period_goals") }} as pg1
            on r.layer = pg1.layer
            and r.indicator = pg1.topline_indicator
            and r.aggregation_hash = pg1.aggregation_hash
            and r.period_type = pg1.period_type
            and r.period_label = pg1.period_label
            and r.academic_year = pg1.academic_year
            and r.has_goal
        left join
            {{ ref("stg_google_sheets__topline_period_goals") }} as pg2
            on r.layer = pg2.layer
            and r.indicator = pg2.topline_indicator
            and r.aggregation_hash = pg2.aggregation_hash
            and r.period_type = pg2.period_type
            and r.period_label = pg2.period_label
            and pg2.academic_year is null
            and r.has_goal
        left join
            {{ ref("stg_google_sheets__topline_period_goals") }} as pg3
            on r.layer = pg3.layer
            and r.indicator = pg3.topline_indicator
            and r.aggregation_hash = pg3.aggregation_hash
            and r.period_type = pg3.period_type
            and r.academic_year = pg3.academic_year
            and pg3.period_label is null
            and r.has_goal
        left join
            {{ ref("stg_google_sheets__topline_period_goals") }} as pg4
            on r.layer = pg4.layer
            and r.indicator = pg4.topline_indicator
            and r.aggregation_hash = pg4.aggregation_hash
            and r.period_type = pg4.period_type
            and pg4.period_label is null
            and pg4.academic_year is null
            and r.has_goal
    )
```

Final select: the current file's goal math verbatim, once, with every `goal`
reference replaced by `goal_resolved`, and `goal_resolved` output under the
column name `goal` (so downstream contracts are unchanged). The `region` column
is city-normalized end to end (Task 4b) — staff week rows change from long
business-unit names to city names/`TAF`, per the amended regression invariant in
Global Constraints. Drop the internal `scope_key` helper by enumerating the
final projection (the canonical list minus the helper, plus the derived goal
columns).

- [ ] **Step 1: Capture the regression baseline BEFORE editing.** Save current
      prod output aggregates (BigQuery MCP):

```sql
select
    metric_type, academic_year, org_level, layer, indicator,
    count(*) as row_count,
    round(sum(coalesce(metric_aggregate_value, 0)), 3) as value_sum,
from `teamster-332318`.kipptaf_topline.int_topline__dashboard_aggregations
group by metric_type, academic_year, org_level, layer, indicator
```

Save the result to `.claude/scratch/topline-regression-baseline.csv` (local
only).

- [ ] **Step 2: Rewrite the model** following the CTE structure above. The
      existing six GROUP BY blocks are preserved verbatim except for (a) the two
      added period columns and (b) the staff blocks switching from
      `m.home_business_unit_name` to `m.region` in select, join, and group by;
      the goal math moves to a single final select. This is the largest step —
      reread `src/dbt/CLAUDE.md` SQL conventions before writing, and keep the
      existing blocks' column order.

- [ ] **Step 3: Properties yml** — set materialization and PK:

```yaml
models:
  - name: int_topline__dashboard_aggregations
    config:
      materialized: table
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - metric_type
              - academic_year
              - org_level
              - region
              - schoolid
              - layer
              - indicator
              - discipline
              - aggregation_hash
              - period_type
              - term
```

Add model + column descriptions for every output column (existing and new).

- [ ] **Step 4: Build and run the regression check**

```bash
uv run dbt build --select int_topline__dashboard_aggregations \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: PASS. Then re-run the Step 1 baseline query against the dev table with
`where period_type = 'week'` added — every (metric_type, academic_year,
org_level, layer, indicator) group's `row_count` and `value_sum` must match the
baseline exactly. Investigate any diff before proceeding; do not rationalize
mismatches.

- [ ] **Step 5: YTD reconciliation.** For period-scoped indicators, ytd rows
      must match the most recent complete week's as-of values within rounding:

```sql
select w.indicator, w.schoolid,
    w.metric_aggregate_value as week_value,
    y.metric_aggregate_value as ytd_value,
from `<dev>`.int_topline__dashboard_aggregations as w
inner join `<dev>`.int_topline__dashboard_aggregations as y
    on w.indicator = y.indicator
    and w.aggregation_hash = y.aggregation_hash
    and w.academic_year = y.academic_year
    and y.period_type = 'ytd'
where w.period_type = 'week'
    and w.is_most_recent_complete_period
    and w.indicator in ('ADA', 'Suspensions', 'Successful Contacts')
    and abs(w.metric_aggregate_value - y.metric_aggregate_value) > 0.005
```

Expected: 0 rows (small tolerance for the current-week vs complete-week
boundary; investigate anything larger).

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/topline
git commit -m "feat(kipptaf): multi-grain topline dashboard aggregations

Refs #4363"
```

---

### Task 11: Update the Tableau extract

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__topline_cascade_dashboard.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__topline_cascade_dashboard.yml`

**Interfaces:**

- Consumes: Task 10 output.
- Produces: existing extract columns + `period_type`, `period_label`,
  `is_current_period`, `is_most_recent_complete_period`.

- [ ] **Step 1: Update the SQL.** Add to the select list (after
      `db.is_current_week,`):

```sql
    db.period_type,
    db.period_label,
    db.is_current_period,
    db.is_most_recent_complete_period,
```

Remove the region decode CASE
(`rpt_tableau__topline_cascade_dashboard.sql:39-47`) entirely — `region` is
city-normalized upstream (Task 4b); replace with a plain `db.region,` in the
column enumeration (plain refs group, per ST06). Note the new region values
`TAF` (central-office staff) and `Paterson` (staff) now flow to the workbook's
region filter.

Replace the inline `is_most_recent_complete_week` computation
(`rpt_tableau__topline_cascade_dashboard.sql:32-37`) with a passthrough that
preserves the legacy column for week rows:

```sql
    if(
        db.period_type = 'week' and db.is_most_recent_complete_period,
        true,
        false
    ) as is_most_recent_complete_week,
```

- [ ] **Step 2: Update the contract yml** — add the four new columns
      (`period_type` string, `period_label` string, `is_current_period` boolean,
      `is_most_recent_complete_period` boolean) with descriptions; add
      descriptions to the model entry noting the Tableau contract: every
      worksheet must filter `period_type` or aggregates mix grains.

- [ ] **Step 3: Build and regression-check**

```bash
uv run dbt build --select rpt_tableau__topline_cascade_dashboard \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: PASS. Verify with BigQuery MCP that
`where period_type = 'week' and is_most_recent_complete_week` returns the same
row count as prod's `where is_most_recent_complete_week`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/extracts
git commit -m "feat(kipptaf): expose period grains in topline cascade extract

Refs #4363"
```

---

### Task 12: Full validation, lint, PR

- [ ] **Step 1: Full downstream build**

```bash
uv run dbt build --select int_topline__periods+ \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: all models and tests PASS.

- [ ] **Step 2: Lint everything changed**

```bash
.trunk/tools/trunk check --force \
  $(git diff --name-only origin/main...HEAD | tr '\n' ' ')
```

Expected: no issues (sqlfluff fires here, not at commit).

- [ ] **Step 3: Push and open the PR** using `.github/pull_request_template.md`
      as the body skeleton. Body must include: `Closes #4363`, the two
      documented deviations (CA Interventions as_of; i-Ready week-assigned
      months), the intentional region change (staff rows: long business-unit
      names → city names/`TAF`; staff region-level `aggregation_hash` /
      `aggregation_display` values shift), the regression + ytd reconciliation
      evidence (aggregate counts only — NO PII), and the deployment coordination
      notes: (a) user re-runs `stage_external_sources` against prod is NOT
      needed (Dagster rematerializes the sheet asset), (b) confirm dbt Cloud CI
      is terminal before pushing fixes, (c) after merge the Tableau workbook
      needs a `period_type` filter added before stakeholders use non-week rows,
      and its region filter/aliases should be checked for the new `TAF` and
      `Paterson` staff values.

- [ ] **Step 4: After dbt Cloud CI passes**, fetch warnings with
      `mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` before
      declaring done.

---

### Task 13: Sheet cutover (DEFERRED — separate PR, after stakeholders populate real data)

Replaces the mock seeds with the real Google Sheet tab and column. Do NOT start
until the user says the sheet data is ready.

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__topline_period_goals.sql`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__topline_aggregate_goals.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/intermediate/int_google_sheets__topline_aggregate_goals.sql`
  (+ its properties yml)
- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__dashboard_aggregations.sql`
- Create:
  `src/dbt/kipptaf/tests/topline/test_topline_period_rollup_consistency.sql`
- Delete: `src/dbt/kipptaf/seeds/seed_topline_period_goals.csv`,
  `src/dbt/kipptaf/seeds/seed_topline_period_rollup.csv`,
  `src/dbt/kipptaf/seeds/properties.yml`

- [ ] **Step 1 (USER/Ops): Add `period_rollup` column to the aggregate goals
      tab** (spreadsheet `1as2rMlr8Z6r9-aI3auBLQ-g79-l-NNarHphGN14_IV0`). Header
      exactly `period_rollup`, values `as_of` or `period` on every row. Source
      of truth for assignments: `seed_topline_period_rollup.csv` on this branch.

- [ ] **Step 2 (USER/Ops): Create tab
      `src_google_sheets__topline_period_goals`** with header row:
      `org_level, entity, schoolid, grade_low, grade_high,     layer, topline_indicator, academic_year, period_type, period_label,     goal`.
      Semantics: entity keys mirror the aggregate goals tab (city names only —
      Newark / Camden / Miami / Paterson / TAF); `academic_year` start-year,
      blank = every year; `period_type` one of week / month / quarter / ytd;
      `period_label` full month name or Q1-Q4, blank = every instance; `goal`
      numeric. Populate real goals (the seed CSV shows the shape).

- [ ] **Step 3 (USER/Ops, cosmetic, any time): normalize `entity` on Outstanding
      Teammates rows** to city names (`TEAM Academy Charter     School` to
      `Newark`, `KIPP Cooper Norcross Academy` to `Camden`, `KIPP Miami` to
      `Miami`, `KIPP Paterson` to `Paterson`,
      `KIPP TEAM and     Family Schools Inc.` to `TAF`). Non-blocking — staging
      normalizes either form via `region_to_city`.

- [ ] **Step 4: Add the source entry** to `sources-external.yml` (after the
      `src_google_sheets__topline__enrollment_targets` entry). Declared
      `columns:` are REQUIRED — `academic_year` and `period_label` are sparse
      and autodetect drops all-NULL columns:

```yaml
- name: src_google_sheets__topline__period_goals
  external:
    options:
      format: GOOGLE_SHEETS
      uris:
        - https://docs.google.com/spreadsheets/d/1as2rMlr8Z6r9-aI3auBLQ-g79-l-NNarHphGN14_IV0
      sheet_range: src_google_sheets__topline_period_goals
      skip_leading_rows: 1
  config:
    meta:
      dagster:
        asset_key:
          - kipptaf
          - google
          - sheets
          - topline
          - period_goals
  columns:
    - name: org_level
      data_type: STRING
    - name: entity
      data_type: STRING
    - name: schoolid
      data_type: INT64
    - name: grade_low
      data_type: INT64
    - name: grade_high
      data_type: INT64
    - name: layer
      data_type: STRING
    - name: topline_indicator
      data_type: STRING
    - name: academic_year
      data_type: INT64
    - name: period_type
      data_type: STRING
    - name: period_label
      data_type: STRING
    - name: goal
      data_type: FLOAT64
```

- [ ] **Step 5: Swap the staging `from`.** In
      `stg_google_sheets__topline_period_goals.sql`, replace the seed ref (and
      its TODO comment) with the source:

```sql
        from
            {{
                source(
                    "google_sheets", "src_google_sheets__topline__period_goals"
                )
            }}
```

- [ ] **Step 6: Route `period_rollup` through the base goals chain.** (a)
      Declare the column in the staging contract yml:

```yaml
- name: period_rollup
  description:
    Per-indicator rollup treatment for non-week grains. as_of takes the last
    available week's value inside each period; period recomputes the metric
    within the period window from date-bearing sources. Blank defaults to as_of
    downstream.
  data_type: string
  data_tests:
    - accepted_values:
        arguments:
          values: [as_of, period]
        config:
          severity: error
```

(b) Pass through `int_google_sheets__topline_aggregate_goals.sql` (ST06: with
the simple functions):

```sql
    coalesce(g.period_rollup, 'as_of') as period_rollup,
```

(c) Repoint `rollup_config` in `int_topline__dashboard_aggregations.sql` (remove
the TODO comment):

```sql
    rollup_config as (
        select distinct layer, topline_indicator, period_rollup,
        from {{ ref("int_google_sheets__topline_aggregate_goals") }}
    ),
```

(d) Add the consistency singular test
`src/dbt/kipptaf/tests/topline/test_topline_period_rollup_consistency.sql` (one
`period_rollup` value per indicator):

```sql
select layer, topline_indicator,
from {{ ref("int_google_sheets__topline_aggregate_goals") }}
group by layer, topline_indicator
having count(distinct period_rollup) > 1
```

- [ ] **Step 7: Delete the seeds** (`git rm` the three files under
      `src/dbt/kipptaf/seeds/`).

- [ ] **Step 8 (USER): Stage the new external for CI** (classifier-blocked for
      Claude; run after the source entry is committed on the cutover branch):

```bash
uv run dbt run-operation stage_external_sources \
  --args "select: google_sheets.src_google_sheets__topline__period_goals" \
  --vars '{ext_full_refresh: true}' \
  --target staging --project-dir src/dbt/kipptaf
```

- [ ] **Step 9: Rebuild and verify.** Build
      `stg_google_sheets__topline_period_goals+` and
      `int_topline__dashboard_aggregations` in dev; verify goal resolution
      counts match expectations (rows with a period-goal override before vs
      after should reflect the real sheet, not the mock). Post-merge, the prod
      external picks up the tab on the next Dagster sheet materialization (all
      tabs on this URI trigger together).
