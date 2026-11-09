# Promo Status Policy Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild promotional status so region/grade policies live in a Google
Sheet rule table (OR-of-ANDs) that regional leaders edit, replacing ~600 lines
of hardcoded CASE logic.

**Architecture:** A fixed numeric metric layer
(`int_students__promotional_status_metrics`, table) feeds an evaluation engine
(`int_students__promotional_status`, view) that unpivots metrics, joins a policy
staging model, and aggregates rule groups twice (attendance/academic, then
overall via pseudo-metrics). Output contract matches the legacy
`int_reporting__promotional_status` exactly.

**Tech Stack:** dbt (BigQuery), Google Sheets external table, dbt unit tests,
singular tests.

**Spec:**
`docs/superpowers/specs/2026-07-02-promo-status-policy-engine-design.md`
**Issue:** #4324. **Branch:**
`anthonygwalters/feat/claude-promo-status-policy-engine` (already checked out in
the main repo — no worktree).

## Global Constraints

- Python/dbt always via `uv run`; never bare `dbt`.
- All dbt commands from repo root with `--project-dir src/dbt/kipptaf`; dev
  builds add `--target dev --defer --state target/prod`.
- SQL follows `.trunk/config/.sqlfluff`: BigQuery dialect, 88-char lines,
  trailing commas in SELECT, single quotes, no `ORDER BY` in models, no
  `GROUP BY ALL`, ST06 column ordering (plain refs → functions → CASE).
- Staging-layer tests set `config: severity: error` explicitly (project default
  is `warn`).
- Generic tests use `arguments:` nesting (dbt 1.11+).
- Commit messages: conventional commits. Do not run `trunk fmt`/`check` manually
  except the final `.trunk/tools/trunk check --force` verification.
- PII: never paste student-level query output into PRs/issues; aggregates OK.
- `current_academic_year` var = 2025 (SY25-26).
- Do NOT modify `.claude/`, hook scripts, or `.devcontainer/`.

---

### Task 1: Metric catalog macro

**Files:**

- Create: `src/dbt/kipptaf/macros/promo_status.sql`

**Interfaces:**

- Produces: `promo_status_metric_columns()` → list of 15 metric column-name
  strings; `promo_status_pseudo_metric_columns()` → list of 2 pseudo-metric
  names. Consumed by Tasks 3 (singular test), 5 (unpivot).

- [ ] **Step 1: Write the macro**

```sql
{% macro promo_status_metric_columns() %}
    {{
        return(
            [
                "ada_term_running",
                "n_absences_y1_running",
                "n_absences_y1_running_non_susp",
                "n_absences_y1_running_non_susp_no_tardy",
                "iready_reading_levels_below",
                "iready_math_levels_below",
                "dibels_composite_level",
                "star_ela_level",
                "star_math_level",
                "fast_ela_level",
                "fast_math_level",
                "n_failing",
                "n_failing_core",
                "projected_credits_y1_term",
                "projected_credits_cum",
            ]
        )
    }}
{% endmacro %}

{% macro promo_status_pseudo_metric_columns() %}
    {{ return(["is_off_track_attendance", "is_off_track_academic"]) }}
{% endmacro %}
```

- [ ] **Step 2: Verify it parses**

Run: `uv run dbt parse --project-dir src/dbt/kipptaf` Expected: exit 0, no Jinja
errors.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/macros/promo_status.sql
git commit -m "feat(kipptaf): add promo status metric catalog macro"
```

---

### Task 2: Replace the disabled cutoffs source with the policies source

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml` (the
  `src_google_sheets__reporting__promo_status_cutoffs` entry, ~line 1374)
- Delete:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__reporting__promo_status_cutoffs.sql`
- Delete:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__reporting__promo_status_cutoffs.yml`

**Interfaces:**

- Produces: source
  `source("google_sheets", "src_google_sheets__reporting__promo_status_policies")`
  with 12 declared snake_case columns (positional mapping — declared names win
  over sheet headers). Consumed by Task 3.

**Context:** The Google Sheet tab + named range
`src_google_sheets__reporting__promo_status_policies` already exists on
spreadsheet `1bRd3cI3WlTdizm5ja7IxGxGjJDzXrOX6i2G731h9yr8` with one sample row.
Dagster sheet assets are auto-generated from the dbt manifest
(`code_locations/kipptaf/google/sheets/assets.py`) — no Python change. Google
Sheets externals with `skip_leading_rows: 1` and an explicit schema map columns
**by position**, so the tab's column ORDER must be exactly the order below (Step
4 verifies).

- [ ] **Step 1: Replace the source entry**

Replace the entire `src_google_sheets__reporting__promo_status_cutoffs` block
(its `config:` with `enabled: false` through `skip_leading_rows: 1`) with:

```yaml
- name: src_google_sheets__reporting__promo_status_policies
  config:
    meta:
      dagster:
        asset_key:
          - kipptaf
          - google
          - sheets
          - reporting
          - promo_status_policies
  external:
    options:
      format: GOOGLE_SHEETS
      uris:
        - https://docs.google.com/spreadsheets/d/1bRd3cI3WlTdizm5ja7IxGxGjJDzXrOX6i2G731h9yr8
      sheet_range: src_google_sheets__reporting__promo_status_policies
      skip_leading_rows: 1
  columns:
    - name: academic_year
      data_type: INT64
    - name: region
      data_type: STRING
    - name: grade_min
      data_type: INT64
    - name: grade_max
      data_type: INT64
    - name: term_name
      data_type: STRING
    - name: domain
      data_type: STRING
    - name: rule_group
      data_type: INT64
    - name: metric
      data_type: STRING
    - name: comparator
      data_type: STRING
    - name: value
      data_type: FLOAT64
    - name: if_missing
      data_type: STRING
    - name: detail_label
      data_type: STRING
```

Match the indentation of sibling entries (the block sits under `tables:`). Note
`columns:` is at the same level as `external:` — nesting it inside `external:`
silently no-ops back to autodetect.

- [ ] **Step 2: Delete the disabled cutoffs staging model and properties**

```bash
git rm src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__reporting__promo_status_cutoffs.sql
git rm src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__reporting__promo_status_cutoffs.yml
```

- [ ] **Step 3: Stage the external table (dev + staging targets)**

```bash
uv run dbt run-operation stage_external_sources \
  --args "select: google_sheets.src_google_sheets__reporting__promo_status_policies" \
  --target dev --project-dir src/dbt/kipptaf
uv run dbt run-operation stage_external_sources \
  --args "select: google_sheets.src_google_sheets__reporting__promo_status_policies" \
  --target staging --project-dir src/dbt/kipptaf
```

Expected: both report the table created (new tables — no `ext_full_refresh`
needed). The `--target staging` run writes to the shared `zz_stg` dataset; if
the permission classifier blocks it, hand that one command to the user — dbt
Cloud CI cannot pass without it.

- [ ] **Step 4: Verify positional column mapping against the live tab**

```bash
uv run dbt show --inline "select * from {{ source('google_sheets', 'src_google_sheets__reporting__promo_status_policies') }} limit 5" \
  --target dev --project-dir src/dbt/kipptaf
```

Expected: the sample row's values land in the right columns (e.g. `region` shows
a region name, `value` shows a number). If values are shifted, the tab's column
order differs from the source declaration — STOP and ask the user to reorder the
tab columns to: `academic_year`, `region`, `grade_min`, `grade_max`,
`term_name`, `domain`, `rule_group`, `metric`, `comparator`, `value`,
`if_missing`, `detail_label`.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/google/sheets/sources-external.yml
git commit -m "feat(kipptaf): add promo status policies sheet source, drop cutoffs"
```

---

### Task 3: Policies staging model

**Files:**

- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__reporting__promo_status_policies.sql`
- Create:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__reporting__promo_status_policies.yml`
- Create:
  `src/dbt/kipptaf/tests/stg_google_sheets__reporting__promo_status_policies__metric_in_catalog.sql`
- Create:
  `src/dbt/kipptaf/tests/stg_google_sheets__reporting__promo_status_policies__detail_label_consistent.sql`

**Interfaces:**

- Consumes: Task 2 source; Task 1 macros.
- Produces: `ref("stg_google_sheets__reporting__promo_status_policies")` — one
  row per condition, columns exactly as the source declaration
  (`academic_year int64, region string, grade_min int64, grade_max int64, term_name string, domain string, rule_group int64, metric string, comparator string, value float64, if_missing string, detail_label string`).
  Consumed by Tasks 5 and 6.

- [ ] **Step 1: Write the staging model**

```sql
select
    academic_year,
    region,
    grade_min,
    grade_max,
    term_name,
    domain,
    rule_group,
    metric,
    comparator,
    `value`,
    if_missing,
    detail_label,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__reporting__promo_status_policies",
        )
    }}
/* google sheets externals surface the sheet's full grid as null rows */
where academic_year is not null
```

If sqlfluff/BigQuery rejects any bare column name as a keyword at Step 4,
backtick it in the SQL and add `quote: true` for that column in the yml.

- [ ] **Step 2: Write the properties yml**

Staging directory defaults (from `dbt_project.yml`) already apply
`materialized: table` and `contract: enforced: true` — don't repeat them.

```yaml
models:
  - name: stg_google_sheets__reporting__promo_status_policies
    description: >-
      Promotional status policy rules, one row per condition, maintained by
      regional leaders in Google Sheets. Conditions sharing a rule_group within
      the same scope (academic_year, region, grade range, term, domain) are
      ANDed together; rule groups are ORed. A student is Off-Track for a domain
      when any fully-satisfied rule group matches their scope.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - academic_year
              - region
              - grade_min
              - grade_max
              - term_name
              - domain
              - rule_group
              - metric
              - comparator
          config:
            severity: error
      - dbt_utils.expression_is_true:
          arguments:
            expression: grade_min <= grade_max
          config:
            severity: error
      - dbt_utils.expression_is_true:
          arguments:
            expression: >-
              metric not in ('is_off_track_attendance', 'is_off_track_academic')
              or domain = 'overall'
          config:
            severity: error
    columns:
      - name: academic_year
        data_type: int64
        description: >-
          Starting calendar year of the school year the rule applies to (2025 =
          SY25-26).
        data_tests:
          - not_null:
              config:
                severity: error
      - name: region
        data_type: string
        description: Region the rule applies to.
        data_tests:
          - not_null:
              config:
                severity: error
          - accepted_values:
              arguments:
                values: [Camden, Newark, Miami, Paterson]
              config:
                severity: error
      - name: grade_min
        data_type: int64
        description: Lowest grade level in scope. Kindergarten is 0.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: grade_max
        data_type: int64
        description: >-
          Highest grade level in scope, inclusive. Equal to grade_min for a
          single-grade rule.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: term_name
        data_type: string
        description: >-
          Reporting term the rule applies to, or All for every term. Term-scaled
          thresholds are one row per term.
        data_tests:
          - not_null:
              config:
                severity: error
          - accepted_values:
              arguments:
                values: [Q1, Q2, Q3, Q4, All]
              config:
                severity: error
      - name: domain
        data_type: string
        description: >-
          Status the rule feeds — attendance, academic, or overall. Overall
          rules may reference the pseudo-metrics is_off_track_attendance and
          is_off_track_academic.
        data_tests:
          - not_null:
              config:
                severity: error
          - accepted_values:
              arguments:
                values: [attendance, academic, overall]
              config:
                severity: error
      - name: rule_group
        data_type: int64
        description: >-
          Grouping integer within a scope and domain. Conditions in the same
          group must ALL be met for the group to fire; the domain is Off-Track
          when ANY group fires.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: metric
        data_type: string
        description: >-
          Metric the condition tests, from the fixed catalog defined by the
          promo_status_metric_columns macro (plus pseudo-metrics for the overall
          domain).
        data_tests:
          - not_null:
              config:
                severity: error
      - name: comparator
        data_type: string
        description: Comparison operator applied as metric comparator value.
        data_tests:
          - not_null:
              config:
                severity: error
          - accepted_values:
              arguments:
                values:
                  - less_than
                  - less_than_or_equal
                  - greater_than
                  - greater_than_or_equal
                  - equals
                  - not_equals
              config:
                severity: error
      - name: value
        data_type: float64
        description: Cutoff value the metric is compared against.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: if_missing
        data_type: string
        description: >-
          What the condition evaluates to when the student has no value for the
          metric — met or not_met. Makes null handling explicit.
        data_tests:
          - not_null:
              config:
                severity: error
          - accepted_values:
              arguments:
                values: [met, not_met]
              config:
                severity: error
      - name: detail_label
        data_type: string
        description: >-
          Optional label emitted as attendance_status_hs_detail when an
          attendance-domain rule group fires. When several labeled groups fire,
          the lowest rule_group number wins.
```

- [ ] **Step 3: Write the metric-catalog singular test**

`src/dbt/kipptaf/tests/stg_google_sheets__reporting__promo_status_policies__metric_in_catalog.sql`:

```sql
{{ config(severity="error") }}

select
    academic_year,
    region,
    domain,
    metric,
from {{ ref("stg_google_sheets__reporting__promo_status_policies") }}
where
    metric not in (
        {% for m in promo_status_metric_columns() + promo_status_pseudo_metric_columns() %}
            '{{ m }}'{% if not loop.last %},{% endif %}
        {% endfor %}
    )
```

- [ ] **Step 4: Write the label-consistency singular test**

`src/dbt/kipptaf/tests/stg_google_sheets__reporting__promo_status_policies__detail_label_consistent.sql`:

```sql
{{ config(severity="error") }}

select
    academic_year,
    region,
    grade_min,
    grade_max,
    term_name,
    domain,
    rule_group,

    count(distinct detail_label) as n_labels,
from {{ ref("stg_google_sheets__reporting__promo_status_policies") }}
group by
    academic_year, region, grade_min, grade_max, term_name, domain, rule_group
having count(distinct detail_label) > 1
```

- [ ] **Step 5: Build and test**

```bash
uv run dbt build \
  --select stg_google_sheets__reporting__promo_status_policies \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

Expected: model builds. Tests pass IF the user's sample row uses valid enum
values; if `accepted_values` / `metric_in_catalog` fail on the sample row, that
is correct behavior — note it and continue (Task 7 replaces the sample with the
real seed; the sample row must be deleted then).

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/google/sheets/staging/ src/dbt/kipptaf/tests/
git commit -m "feat(kipptaf): add promo status policies staging model"
```

---

### Task 4: Metric layer model

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__promotional_status_metrics.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__promotional_status_metrics.yml`
- Read (source of copied CTEs — do NOT delete yet):
  `src/dbt/kipptaf/models/reporting/intermediate/int_reporting__promotional_status.sql`

**Interfaces:**

- Produces: `ref("int_students__promotional_status_metrics")` — one row per
  `student_number × academic_year × term_name`, all years. Columns:
  `student_number int64, academic_year int64, region string, grade_level int64, term_name string, is_current boolean` +
  the 15 catalog metrics
  (`ada_term_running float64, n_absences_y1_running float64, n_absences_y1_running_non_susp float64, n_absences_y1_running_non_susp_no_tardy float64, iready_reading_levels_below int64, iready_math_levels_below int64, dibels_composite_level int64, star_ela_level int64, star_math_level int64, fast_ela_level int64, fast_math_level int64, n_failing int64, n_failing_core int64, projected_credits_y1_term float64, projected_credits_cum float64`) +
  display/override columns
  (`iready_reading_recent string, iready_math_recent string, dibels_composite_level_recent_str string, exemption string, manual_retention string`).
  Consumed by Tasks 5, 6.

- [ ] **Step 1: Write the model**

Copy these CTEs **verbatim** from the legacy
`int_reporting__promotional_status.sql` (they are unchanged): `credits`,
`iready_dr`, `iready`, `mclass`, `star_results`, `star`, `fast_results`, `fast`,
`ps_log`, `exempt_override`, `force_retention`. Copy the `attendance` CTE but
DELETE its two trailing computed columns (`hs_at_risk_absences` and
`hs_off_track_absences` CASE expressions) — the sheet now owns those thresholds.
Then replace the legacy `promo` CTE and final select with this single final
select (the FROM/JOIN block is the legacy `promo` CTE's, unchanged):

```sql
select
    co.student_number,
    co.academic_year,
    co.region,
    co.grade_level,

    rt.name as term_name,
    rt.is_current,

    att.ada_term_running,
    att.n_absences_y1_running,
    att.n_absences_y1_running_non_susp,
    att.n_absences_y1_running_non_susp_no_tardy,

    ir.iready_reading_recent,
    ir.iready_math_recent,

    c.n_failing,
    c.n_failing_core,
    c.projected_credits_y1_term,
    c.projected_credits_cum,

    m.measure_standard_level as dibels_composite_level_recent_str,
    m.measure_standard_level_int as dibels_composite_level,

    s.star_ela_level,
    s.star_math_level,

    f.fast_ela as fast_ela_level,
    f.fast_math as fast_math_level,

    if(fr.entry_date is not null, 'Manual Retention', null) as manual_retention,

    case
        ir.iready_reading_recent
        when '3 or More Grade Levels Below'
        then 3
        when '2 Grade Levels Below'
        then 2
        when '1 Grade Level Below'
        then 1
        when 'Early On Grade Level'
        then 0
        when 'Mid or Above Grade Level'
        then 0
    end as iready_reading_levels_below,

    case
        ir.iready_math_recent
        when '3 or More Grade Levels Below'
        then 3
        when '2 Grade Levels Below'
        then 2
        when '1 Grade Level Below'
        then 1
        when 'Early On Grade Level'
        then 0
        when 'Mid or Above Grade Level'
        then 0
    end as iready_math_levels_below,

    case
        when
            co.grade_level < 3
            and co.is_self_contained
            and co.special_education_code in ('CMI', 'CMO', 'CSE')
        then 'Exempt - Special Education'
        when
            co.grade_level between 3 and 8
            and (
                nj.state_assessment_name = '3'
                or nj.math_state_assessment_name in ('3', '4')
            )
        then 'Exempt - Special Education'
        when lg.entry_date is not null
        then 'Exempt - Manual Override'
    end as exemption,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on co.academic_year = rt.academic_year
    and co.schoolid = rt.school_id
    and rt.type = 'RT'
left join
    attendance as att
    on co.studentid = att.studentid
    and co.yearid = att.yearid
    and rt.name = att.term_name
    and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
left join
    credits as c
    on co.studentid = c.studentid
    and co.academic_year = c.academic_year
    and rt.name = c.storecode
    and {{ union_dataset_join_clause(left_alias="co", right_alias="c") }}
left join
    iready as ir
    on co.student_number = ir.student_id
    and co.academic_year = ir.academic_year_int
left join
    mclass as m
    on co.academic_year = m.academic_year
    and co.student_number = m.student_number
    and m.rn_composite = 1
left join
    star as s
    on co.student_number = s.student_display_id
    and co.academic_year = s.academic_year
left join
    fast as f on co.fleid = f.student_id and co.academic_year = f.academic_year
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as nj
    on co.students_dcid = nj.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
left join
    exempt_override as lg
    on co.studentid = lg.studentid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="lg") }}
    and co.academic_year = lg.academic_year
    and lg.rn_log = 1
left join
    force_retention as fr
    on co.studentid = fr.studentid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="fr") }}
    and co.academic_year = fr.academic_year
    and fr.rn_log = 1
where co.rn_year = 1
```

- [ ] **Step 2: Write the properties yml**

```yaml
models:
  - name: int_students__promotional_status_metrics
    description: >-
      Metric layer for promotional status — one row per student, academic year,
      and reporting term, carrying every numeric metric the policy engine can
      evaluate plus display strings and the code-owned exemption and
      manual-retention overrides. Computed for all academic years. Metrics are
      numeric so sheet-driven conditions are uniformly metric, comparator,
      value.
    config:
      materialized: table
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - academic_year
              - term_name
    columns:
      - name: student_number
        data_type: int64
        description: Student number assigned by the school.
        config:
          meta:
            contains_pii: true
      - name: academic_year
        data_type: int64
        description: Starting calendar year of the school year.
      - name: region
        data_type: string
        description: Student region, used to scope policy rules.
      - name: grade_level
        data_type: int64
        description: Grade level, used to scope policy rules. K is 0.
      - name: term_name
        data_type: string
        description: Reporting term name (Q1-Q4).
      - name: is_current
        data_type: boolean
        description: >-
          True if this is the most recent completed or active reporting term.
      - name: ada_term_running
        data_type: float64
        description: >-
          Average daily attendance rate accumulated through the end of the term.
      - name: n_absences_y1_running
        data_type: float64
        description: >-
          Total absences year-to-date through the end of the term, including
          suspensions.
      - name: n_absences_y1_running_non_susp
        data_type: float64
        description: >-
          Absences year-to-date excluding suspension codes, plus a tardy penalty
          of floor(tardies / 3).
      - name: n_absences_y1_running_non_susp_no_tardy
        data_type: float64
        description: >-
          Absences year-to-date excluding suspension codes with no tardy penalty
          applied.
      - name: iready_reading_recent
        data_type: string
        description:
          Most recent iReady reading overall relative placement label.
      - name: iready_math_recent
        data_type: string
        description: Most recent iReady math overall relative placement label.
      - name: iready_reading_levels_below
        data_type: int64
        description: >-
          Most recent iReady reading placement as grade levels below — 3 for
          three or more below, 2, 1, and 0 for on or above grade level. NULL
          when the student has no result.
      - name: iready_math_levels_below
        data_type: int64
        description: >-
          Most recent iReady math placement as grade levels below — 3 for three
          or more below, 2, 1, and 0 for on or above grade level. NULL when the
          student has no result.
      - name: dibels_composite_level_recent_str
        data_type: string
        description: Most recent DIBELS composite benchmark level label.
      - name: dibels_composite_level
        data_type: int64
        description: >-
          Most recent DIBELS composite benchmark level as an integer (lower is
          more at-risk).
      - name: star_ela_level
        data_type: int64
        description: Most recent Renaissance STAR reading achievement level.
      - name: star_math_level
        data_type: int64
        description: Most recent Renaissance STAR math achievement level.
      - name: fast_ela_level
        data_type: int64
        description: Most recent FAST ELA achievement level (Florida only).
      - name: fast_math_level
        data_type: int64
        description: Most recent FAST math achievement level (Florida only).
      - name: n_failing
        data_type: int64
        description: Number of courses with a failing grade as of the term.
      - name: n_failing_core
        data_type: int64
        description: Number of core courses with a failing grade as of the term.
      - name: projected_credits_y1_term
        data_type: float64
        description: >-
          Projected credits to be earned in the current academic year through
          the term.
      - name: projected_credits_cum
        data_type: float64
        description: >-
          Projected cumulative credits earned through end of year, combining
          projected year credits with historical earned credits.
      - name: exemption
        data_type: string
        description: >-
          Populated when a student is exempt from retention criteria — Exempt -
          Special Education (code-owned SPED rules) or Exempt - Manual Override
          (PowerSchool log entry).
      - name: manual_retention
        data_type: string
        description: >-
          Populated with Manual Retention when a staff member has logged a
          Retain without criteria entry in PowerSchool.
```

- [ ] **Step 3: Build and test**

```bash
uv run dbt build \
  --select int_students__promotional_status_metrics \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

Expected: model builds as a table; uniqueness test passes (warn severity — if it
warns, investigate for cross-district transfer duplicates before proceeding).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/students/
git commit -m "feat(kipptaf): add promotional status metric layer model"
```

---

### Task 5: Evaluation engine model with unit tests

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__promotional_status.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__promotional_status.yml`

**Interfaces:**

- Consumes: Task 4 metrics model; Task 3 policies staging; Task 1 macros.
- Produces: `ref("int_students__promotional_status")` with EXACTLY the legacy
  output contract (see legacy
  `properties/int_reporting__promotional_status.yml`):
  `student_number, academic_year, term_name, is_current, ada_term_running, n_absences_y1_running, n_absences_y1_running_non_susp, n_absences_y1_running_non_susp_no_tardy, iready_reading_recent, iready_math_recent, n_failing, n_failing_core, projected_credits_cum, projected_credits_y1_term, dibels_composite_level_recent_str, dibels_composite_level_recent, star_math_level_recent, star_reading_level_recent, fast_ela_level_recent, fast_math_level_recent, attendance_status, attendance_status_hs_detail, academic_status, exemption, manual_retention, overall_status`.
  Statuses are NULL where no policy rows match. Consumed by Task 8 (rpt swaps).

- [ ] **Step 1: Write the model**

```sql
with
    metrics as (
        select *,
        from {{ ref("int_students__promotional_status_metrics") }}
    ),

    policies as (
        select *,
        from {{ ref("stg_google_sheets__reporting__promo_status_policies") }}
    ),

    metrics_long as (
        select
            student_number,
            academic_year,
            term_name,
            region,
            grade_level,
            metric,
            metric_value,
        from
            (
                select
                    student_number,
                    academic_year,
                    term_name,
                    region,
                    grade_level,

                    {% for m in promo_status_metric_columns() %}
                        cast({{ m }} as float64) as {{ m }},
                    {% endfor %}
                from metrics
            ) unpivot include nulls (
                metric_value for metric in (
                    {% for m in promo_status_metric_columns() %}
                        {{ m }}{% if not loop.last %},{% endif %}
                    {% endfor %}
                )
            )
    ),

    conditions as (
        select
            ml.student_number,
            ml.academic_year,
            ml.term_name,

            p.domain,
            p.grade_min,
            p.grade_max,
            p.rule_group,
            p.detail_label,

            p.term_name as policy_term_name,

            case
                when ml.metric_value is null
                then p.if_missing = 'met'
                when p.comparator = 'less_than'
                then ml.metric_value < p.`value`
                when p.comparator = 'less_than_or_equal'
                then ml.metric_value <= p.`value`
                when p.comparator = 'greater_than'
                then ml.metric_value > p.`value`
                when p.comparator = 'greater_than_or_equal'
                then ml.metric_value >= p.`value`
                when p.comparator = 'equals'
                then ml.metric_value = p.`value`
                when p.comparator = 'not_equals'
                then ml.metric_value != p.`value`
            end as is_met,
        from metrics_long as ml
        inner join
            policies as p
            on ml.academic_year = p.academic_year
            and ml.region = p.region
            and ml.metric = p.metric
            and ml.grade_level between p.grade_min and p.grade_max
            and (ml.term_name = p.term_name or p.term_name = 'All')
            and p.domain in ('attendance', 'academic')
    ),

    rule_groups as (
        select
            student_number,
            academic_year,
            term_name,
            domain,
            grade_min,
            grade_max,
            policy_term_name,
            rule_group,

            logical_and(is_met) as is_fired,
            max(detail_label) as detail_label,
        from conditions
        group by
            student_number,
            academic_year,
            term_name,
            domain,
            grade_min,
            grade_max,
            policy_term_name,
            rule_group
    ),

    domain_status as (
        select
            student_number,
            academic_year,
            term_name,
            domain,

            logical_or(is_fired) as is_off_track,

            array_agg(
                if(is_fired, detail_label, null) ignore nulls
                order by rule_group
                limit 1
            )[safe_offset(0)] as detail_label,
        from rule_groups
        group by student_number, academic_year, term_name, domain
    ),

    domain_wide as (
        select
            student_number,
            academic_year,
            term_name,

            logical_or(
                if(domain = 'attendance', is_off_track, null)
            ) as is_off_track_attendance,

            logical_or(
                if(domain = 'academic', is_off_track, null)
            ) as is_off_track_academic,

            max(
                if(domain = 'attendance', detail_label, null)
            ) as attendance_detail_label,
        from domain_status
        group by student_number, academic_year, term_name
    ),

    overall_metrics_long as (
        select
            student_number,
            academic_year,
            term_name,
            region,
            grade_level,
            metric,
            metric_value,
        from metrics_long

        union all

        select
            m.student_number,
            m.academic_year,
            m.term_name,
            m.region,
            m.grade_level,

            pseudo_metric as metric,

            if(
                pseudo_metric = 'is_off_track_attendance',
                cast(cast(dw.is_off_track_attendance as int) as float64),
                cast(cast(dw.is_off_track_academic as int) as float64)
            ) as metric_value,
        from metrics as m
        cross join
            unnest(
                ['is_off_track_attendance', 'is_off_track_academic']
            ) as pseudo_metric
        left join
            domain_wide as dw
            on m.student_number = dw.student_number
            and m.academic_year = dw.academic_year
            and m.term_name = dw.term_name
    ),

    overall_conditions as (
        select
            ml.student_number,
            ml.academic_year,
            ml.term_name,

            p.grade_min,
            p.grade_max,
            p.rule_group,

            p.term_name as policy_term_name,

            case
                when ml.metric_value is null
                then p.if_missing = 'met'
                when p.comparator = 'less_than'
                then ml.metric_value < p.`value`
                when p.comparator = 'less_than_or_equal'
                then ml.metric_value <= p.`value`
                when p.comparator = 'greater_than'
                then ml.metric_value > p.`value`
                when p.comparator = 'greater_than_or_equal'
                then ml.metric_value >= p.`value`
                when p.comparator = 'equals'
                then ml.metric_value = p.`value`
                when p.comparator = 'not_equals'
                then ml.metric_value != p.`value`
            end as is_met,
        from overall_metrics_long as ml
        inner join
            policies as p
            on ml.academic_year = p.academic_year
            and ml.region = p.region
            and ml.metric = p.metric
            and ml.grade_level between p.grade_min and p.grade_max
            and (ml.term_name = p.term_name or p.term_name = 'All')
            and p.domain = 'overall'
    ),

    overall_rule_groups as (
        select
            student_number,
            academic_year,
            term_name,
            grade_min,
            grade_max,
            policy_term_name,
            rule_group,

            logical_and(is_met) as is_fired,
        from overall_conditions
        group by
            student_number,
            academic_year,
            term_name,
            grade_min,
            grade_max,
            policy_term_name,
            rule_group
    ),

    overall_status as (
        select
            student_number,
            academic_year,
            term_name,

            logical_or(is_fired) as is_off_track,
        from overall_rule_groups
        group by student_number, academic_year, term_name
    )

select
    m.student_number,
    m.academic_year,
    m.term_name,
    m.is_current,
    m.ada_term_running,
    m.n_absences_y1_running,
    m.n_absences_y1_running_non_susp,
    m.n_absences_y1_running_non_susp_no_tardy,
    m.iready_reading_recent,
    m.iready_math_recent,
    m.n_failing,
    m.n_failing_core,
    m.projected_credits_cum,
    m.projected_credits_y1_term,
    m.dibels_composite_level_recent_str,
    m.exemption,
    m.manual_retention,

    m.dibels_composite_level as dibels_composite_level_recent,
    m.star_math_level as star_math_level_recent,
    m.star_ela_level as star_reading_level_recent,
    m.fast_ela_level as fast_ela_level_recent,
    m.fast_math_level as fast_math_level_recent,

    coalesce(
        dw.attendance_detail_label,
        case
            dw.is_off_track_attendance
            when true
            then 'Off-Track'
            when false
            then 'On-Track'
        end
    ) as attendance_status_hs_detail,

    case
        dw.is_off_track_attendance
        when true
        then 'Off-Track'
        when false
        then 'On-Track'
    end as attendance_status,

    case
        dw.is_off_track_academic
        when true
        then 'Off-Track'
        when false
        then 'On-Track'
    end as academic_status,

    case
        os.is_off_track when true then 'Off-Track' when false then 'On-Track'
    end as overall_status,
from metrics as m
left join
    domain_wide as dw
    on m.student_number = dw.student_number
    and m.academic_year = dw.academic_year
    and m.term_name = dw.term_name
left join
    overall_status as os
    on m.student_number = os.student_number
    and m.academic_year = os.academic_year
    and m.term_name = os.term_name
```

Implementation notes:

- `unpivot include nulls` is required — the default excludes NULL metric rows,
  which would break `if_missing` evaluation.
- `case <expr> when true ... when false ...` (no ELSE) deliberately yields NULL
  for NULL input; `if()` would collapse NULL to the else branch.
- `logical_or` / `logical_and` / `max` ignore NULLs, so a student with rules in
  only one domain gets NULL (not false) for the other domain.
- The grouping keys include `grade_min`, `grade_max`, `policy_term_name` so
  overlapping scopes that reuse the same `rule_group` integer stay separate
  groups.

- [ ] **Step 2: Write the properties yml**

Copy the legacy
`src/dbt/kipptaf/models/reporting/intermediate/properties/int_reporting__promotional_status.yml`
column blocks (names, types, descriptions) verbatim, then:

1. Change `name:` to `int_students__promotional_status`.
2. Replace the model `description:` with the text below.
3. Add the model-level `data_tests:` block below (legacy had no uniqueness test
   — this is a required addition).
4. Update the three status-column descriptions to mention NULL semantics (shown
   below).
5. Append the `unit_tests:` block below at file bottom.

Model description:

```yaml
description: >-
  Per-student, per-term promotional status for all active enrollments, evaluated
  from the sheet-driven policy rule table
  (stg_google_sheets__reporting__promo_status_policies). Metrics come from
  int_students__promotional_status_metrics; conditions in a rule group AND
  together, rule groups OR together, and any fired group makes the domain
  Off-Track. The overall domain is evaluated second and may reference the
  attendance and academic outcomes as pseudo-metrics. Statuses are NULL for
  student-terms no policy row matches (e.g. years not yet seeded in the sheet).
  SPED exemptions and PowerSchool log overrides stay code-owned in the metrics
  model.
```

Model-level tests:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - student_number
          - academic_year
          - term_name
```

Status-column description updates (replace the legacy description text for these
three columns; keep `data_type`):

```yaml
- name: attendance_status
  data_type: string
  description: >-
    On-Track or Off-Track from the attendance-domain policy rules matching the
    student's region, grade, year, and term. NULL when no attendance rule
    matches.
- name: academic_status
  data_type: string
  description: >-
    On-Track or Off-Track from the academic-domain policy rules matching the
    student's region, grade, year, and term. NULL when no academic rule matches.
- name: overall_status
  data_type: string
  description: >-
    On-Track or Off-Track from the overall-domain policy rules, which may
    combine the attendance and academic outcomes (as pseudo-metrics) with direct
    metric conditions. NULL when no overall rule matches.
```

Unit tests block (uses `format: sql` — dict fixtures fail schema introspection
for same-PR new models):

```yaml
unit_tests:
  - name: test_promo_status_or_of_ands
    description: >-
      Verifies OR-of-ANDs evaluation and if_missing handling. Student 1 fires
      single-condition group 1 (n_failing_core >= 2). Student 2 fires
      two-condition group 2 (low ADA AND 3+ levels below in reading). Student 3
      partially satisfies group 2 only, so stays On-Track. Student 4 has NULL
      ADA and NULL iReady with if_missing met on both group-2 conditions, so
      fires. Student 5 is in a region with no rules and gets NULL statuses.
    model: int_students__promotional_status
    given:
      - input: ref('int_students__promotional_status_metrics')
        format: sql
        rows: |
          select 1 as student_number, 2025 as academic_year,
            'Q1' as term_name, true as is_current, 'Newark' as region,
            5 as grade_level, 0.95 as ada_term_running,
            0.0 as n_absences_y1_running,
            0.0 as n_absences_y1_running_non_susp,
            0.0 as n_absences_y1_running_non_susp_no_tardy,
            0 as iready_reading_levels_below,
            0 as iready_math_levels_below,
            cast(null as int64) as dibels_composite_level,
            cast(null as int64) as star_ela_level,
            cast(null as int64) as star_math_level,
            cast(null as int64) as fast_ela_level,
            cast(null as int64) as fast_math_level,
            2 as n_failing, 2 as n_failing_core,
            cast(null as float64) as projected_credits_y1_term,
            cast(null as float64) as projected_credits_cum,
            cast(null as string) as iready_reading_recent,
            cast(null as string) as iready_math_recent,
            cast(null as string) as dibels_composite_level_recent_str,
            cast(null as string) as exemption,
            cast(null as string) as manual_retention
          union all
          select 2, 2025, 'Q1', true, 'Newark', 5, 0.80, 0.0, 0.0, 0.0,
            3, 0, null, null, null, null, null, 0, 0, null, null,
            null, null, null, null, null
          union all
          select 3, 2025, 'Q1', true, 'Newark', 5, 0.80, 0.0, 0.0, 0.0,
            1, 0, null, null, null, null, null, 0, 0, null, null,
            null, null, null, null, null
          union all
          select 4, 2025, 'Q1', true, 'Newark', 5,
            cast(null as float64), 0.0, 0.0, 0.0,
            null, null, null, null, null, null, null, 0, 0, null, null,
            null, null, null, null, null
          union all
          select 5, 2025, 'Q1', true, 'Miami', 5, 0.50, 0.0, 0.0, 0.0,
            3, 3, null, null, null, null, null, 5, 5, null, null,
            null, null, null, null, null
      - input: ref('stg_google_sheets__reporting__promo_status_policies')
        format: sql
        rows: |
          select 2025 as academic_year, 'Newark' as region,
            5 as grade_min, 8 as grade_max, 'All' as term_name,
            'academic' as domain, 1 as rule_group,
            'n_failing_core' as metric, 'greater_than_or_equal' as comparator,
            2.0 as `value`, 'not_met' as if_missing,
            cast(null as string) as detail_label
          union all
          select 2025, 'Newark', 5, 8, 'All', 'academic', 2,
            'ada_term_running', 'less_than', 0.85, 'met', null
          union all
          select 2025, 'Newark', 5, 8, 'All', 'academic', 2,
            'iready_reading_levels_below', 'greater_than_or_equal', 3.0, 'met', null
    expect:
      rows:
        - { student_number: 1, academic_status: Off-Track }
        - { student_number: 2, academic_status: Off-Track }
        - { student_number: 3, academic_status: On-Track }
        - { student_number: 4, academic_status: Off-Track }
        - { student_number: 5, academic_status: null }
  - name: test_promo_status_detail_label_term_scope_and_overall
    description: >-
      Verifies term scoping, detail-label precedence, and the overall pseudo
      metric pass. Student 1 (Q1, 30 absences) fires both attendance groups and
      takes the lowest fired group's label; overall ORs attendance and academic
      so it is Off-Track. Student 2 (Q1, 10 absences) fires only the Q1-scoped
      approaching group. Student 3 is in Q2 where the Q1-scoped group does not
      apply and stays On-Track everywhere.
    model: int_students__promotional_status
    given:
      - input: ref('int_students__promotional_status_metrics')
        format: sql
        rows: |
          select 1 as student_number, 2025 as academic_year,
            'Q1' as term_name, true as is_current, 'Newark' as region,
            9 as grade_level, 0.90 as ada_term_running,
            30.0 as n_absences_y1_running,
            30.0 as n_absences_y1_running_non_susp,
            30.0 as n_absences_y1_running_non_susp_no_tardy,
            cast(null as int64) as iready_reading_levels_below,
            cast(null as int64) as iready_math_levels_below,
            cast(null as int64) as dibels_composite_level,
            cast(null as int64) as star_ela_level,
            cast(null as int64) as star_math_level,
            cast(null as int64) as fast_ela_level,
            cast(null as int64) as fast_math_level,
            0 as n_failing, 0 as n_failing_core,
            25.0 as projected_credits_y1_term,
            50.0 as projected_credits_cum,
            cast(null as string) as iready_reading_recent,
            cast(null as string) as iready_math_recent,
            cast(null as string) as dibels_composite_level_recent_str,
            cast(null as string) as exemption,
            cast(null as string) as manual_retention
          union all
          select 2, 2025, 'Q1', true, 'Newark', 9, 0.90, 10.0, 10.0, 10.0,
            null, null, null, null, null, null, null, 0, 0, 25.0, 50.0,
            null, null, null, null, null
          union all
          select 3, 2025, 'Q2', true, 'Newark', 9, 0.90, 10.0, 10.0, 10.0,
            null, null, null, null, null, null, null, 0, 0, 25.0, 50.0,
            null, null, null, null, null
      - input: ref('stg_google_sheets__reporting__promo_status_policies')
        format: sql
        rows: |
          select 2025 as academic_year, 'Newark' as region,
            9 as grade_min, 12 as grade_max, 'All' as term_name,
            'attendance' as domain, 1 as rule_group,
            'n_absences_y1_running_non_susp_no_tardy' as metric,
            'greater_than_or_equal' as comparator, 27.0 as `value`,
            'not_met' as if_missing,
            'Off-Track (Already reached threshold)' as detail_label
          union all
          select 2025, 'Newark', 9, 12, 'Q1', 'attendance', 2,
            'n_absences_y1_running_non_susp_no_tardy', 'greater_than_or_equal',
            6.0, 'not_met', 'Off-Track (Approaching threshold)'
          union all
          select 2025, 'Newark', 9, 12, 'All', 'academic', 1,
            'projected_credits_cum', 'less_than', 25.0, 'not_met', null
          union all
          select 2025, 'Newark', 9, 12, 'All', 'overall', 1,
            'is_off_track_attendance', 'equals', 1.0, 'not_met', null
          union all
          select 2025, 'Newark', 9, 12, 'All', 'overall', 2,
            'is_off_track_academic', 'equals', 1.0, 'not_met', null
    expect:
      rows:
        - {
            student_number: 1,
            attendance_status: Off-Track,
            attendance_status_hs_detail: Off-Track (Already reached threshold),
            academic_status: On-Track,
            overall_status: Off-Track,
          }
        - {
            student_number: 2,
            attendance_status: Off-Track,
            attendance_status_hs_detail: Off-Track (Approaching threshold),
            academic_status: On-Track,
            overall_status: Off-Track,
          }
        - {
            student_number: 3,
            attendance_status: On-Track,
            attendance_status_hs_detail: On-Track,
            academic_status: On-Track,
            overall_status: On-Track,
          }
```

- [ ] **Step 3: Run the unit tests and expect them to pass**

```bash
uv run dbt test --select "int_students__promotional_status,test_type:unit" \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

Expected: both unit tests PASS. If a fixture column mismatch errors, the model
references a metrics column missing from the fixture — add it to the fixture,
don't remove it from the model.

- [ ] **Step 4: Build the model**

```bash
uv run dbt build --select int_students__promotional_status \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

Expected: view builds; uniqueness test passes.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/students/
git commit -m "feat(kipptaf): add sheet-driven promotional status evaluation engine"
```

---

### Task 6: Coverage singular test

**Files:**

- Create:
  `src/dbt/kipptaf/tests/stg_google_sheets__reporting__promo_status_policies__current_year_coverage.sql`

**Interfaces:**

- Consumes: Task 3 policies staging, Task 4 metrics model.

- [ ] **Step 1: Write the test** (warn severity is the project default — no
      config needed)

```sql
with
    enrolled as (
        /* grain projection: every selected column is functionally determined
        by the partition key; not a mask for upstream duplicates */
        select distinct region, grade_level,
        from {{ ref("int_students__promotional_status_metrics") }}
        where academic_year = {{ var("current_academic_year") }}
    )

select
    e.region,
    e.grade_level,

    d as domain,
from enrolled as e
cross join unnest(['attendance', 'academic', 'overall']) as d
left join
    {{ ref("stg_google_sheets__reporting__promo_status_policies") }} as p
    on e.region = p.region
    and e.grade_level between p.grade_min and p.grade_max
    and d = p.domain
    and p.academic_year = {{ var("current_academic_year") }}
where p.rule_group is null
```

- [ ] **Step 2: Run it**

```bash
uv run dbt test \
  --select stg_google_sheets__reporting__promo_status_policies__current_year_coverage \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

Expected: WARN with many rows (sheet holds only a sample row until Task 7) —
that's the test working. After Task 7 the only expected warn rows are Miami
grade 3 attendance and any Paterson grades (see Task 7 notes).

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/tests/
git commit -m "feat(kipptaf): warn on promo status policy coverage gaps"
```

---

### Task 7: Seed the sheet with SY25-26 policies (user handoff)

**Files:** none in repo (Google Sheet edit + rebuild). Write the CSV to
`.claude/scratch/promo_status_policies_seed.csv` for the user.

**Context:** This is the transcription of every hardcoded CASE branch in the
legacy model into rule rows. The engineer writes the CSV; the USER pastes it
into the sheet tab (replacing the sample row — the sample row must be deleted or
made valid, or error-severity staging tests fail CI).

- [ ] **Step 1: Write the seed CSV to
      `.claude/scratch/promo_status_policies_seed.csv`**

```csv
academic_year,region,grade_min,grade_max,term_name,domain,rule_group,metric,comparator,value,if_missing,detail_label
2025,Newark,0,0,All,attendance,1,ada_term_running,less_than,0.85,met,
2025,Newark,1,2,All,attendance,1,ada_term_running,less_than,0.87,met,
2025,Newark,3,8,All,attendance,1,ada_term_running,less_than,0.9,met,
2025,Newark,9,12,All,attendance,1,n_absences_y1_running_non_susp_no_tardy,greater_than_or_equal,27,not_met,Off-Track (Already reached threshold)
2025,Newark,9,12,Q1,attendance,2,n_absences_y1_running_non_susp_no_tardy,greater_than_or_equal,6,not_met,Off-Track (Approaching threshold)
2025,Newark,9,12,Q2,attendance,2,n_absences_y1_running_non_susp_no_tardy,greater_than_or_equal,12,not_met,Off-Track (Approaching threshold)
2025,Newark,9,12,Q3,attendance,2,n_absences_y1_running_non_susp_no_tardy,greater_than_or_equal,18,not_met,Off-Track (Approaching threshold)
2025,Newark,9,12,Q4,attendance,2,n_absences_y1_running_non_susp_no_tardy,greater_than_or_equal,24,not_met,Off-Track (Approaching threshold)
2025,Camden,0,0,All,attendance,1,ada_term_running,less_than,0.82,met,
2025,Camden,1,2,All,attendance,1,ada_term_running,less_than,0.86,met,
2025,Camden,3,8,All,attendance,1,ada_term_running,less_than,0.87,met,
2025,Camden,9,12,All,attendance,1,n_absences_y1_running_non_susp,greater_than_or_equal,36,not_met,Off-Track (Already reached threshold)
2025,Camden,9,12,Q1,attendance,2,n_absences_y1_running_non_susp,greater_than_or_equal,9,not_met,Off-Track (Approaching threshold)
2025,Camden,9,12,Q2,attendance,2,n_absences_y1_running_non_susp,greater_than_or_equal,18,not_met,Off-Track (Approaching threshold)
2025,Camden,9,12,Q3,attendance,2,n_absences_y1_running_non_susp,greater_than_or_equal,27,not_met,Off-Track (Approaching threshold)
2025,Camden,9,12,Q4,attendance,2,n_absences_y1_running_non_susp,greater_than_or_equal,36,not_met,Off-Track (Approaching threshold)
2025,Miami,0,0,All,attendance,1,ada_term_running,less_than,0.8,not_met,
2025,Miami,1,2,All,attendance,1,ada_term_running,less_than,0.85,not_met,
2025,Miami,4,4,All,attendance,1,ada_term_running,less_than,0.85,not_met,
2025,Miami,5,8,All,attendance,1,ada_term_running,less_than,0.85,not_met,
2025,Miami,5,8,All,attendance,2,n_absences_y1_running,greater_than_or_equal,27,not_met,
2025,Newark,0,1,All,academic,1,dibels_composite_level,less_than_or_equal,1,met,
2025,Newark,2,2,All,academic,1,iready_reading_levels_below,greater_than_or_equal,2,met,
2025,Newark,3,8,All,academic,1,iready_reading_levels_below,greater_than_or_equal,2,met,
2025,Newark,3,8,All,academic,1,iready_math_levels_below,greater_than_or_equal,2,met,
2025,Newark,3,8,All,academic,2,n_failing_core,greater_than_or_equal,2,not_met,
2025,Newark,9,9,All,academic,1,projected_credits_cum,less_than,25,not_met,
2025,Newark,10,10,All,academic,1,projected_credits_cum,less_than,50,not_met,
2025,Newark,11,11,All,academic,1,projected_credits_cum,less_than,85,not_met,
2025,Newark,12,12,All,academic,1,projected_credits_cum,less_than,120,not_met,
2025,Camden,0,1,All,academic,1,dibels_composite_level,less_than_or_equal,1,met,
2025,Camden,2,2,All,academic,1,iready_reading_levels_below,greater_than_or_equal,2,met,
2025,Camden,3,8,All,academic,1,iready_reading_levels_below,greater_than_or_equal,2,met,
2025,Camden,3,8,All,academic,1,iready_math_levels_below,greater_than_or_equal,2,met,
2025,Camden,3,8,All,academic,2,n_failing_core,greater_than_or_equal,2,not_met,
2025,Camden,9,9,All,academic,1,projected_credits_cum,less_than,25,not_met,
2025,Camden,10,10,All,academic,1,projected_credits_cum,less_than,50,not_met,
2025,Camden,11,11,All,academic,1,projected_credits_cum,less_than,85,not_met,
2025,Camden,12,12,All,academic,1,projected_credits_cum,less_than,120,not_met,
2025,Miami,0,2,All,academic,1,star_math_level,equals,1,not_met,
2025,Miami,0,2,All,academic,2,star_ela_level,equals,1,not_met,
2025,Miami,3,3,All,academic,1,fast_ela_level,equals,1,not_met,
2025,Miami,4,4,All,academic,1,fast_math_level,equals,1,not_met,
2025,Miami,4,4,All,academic,1,fast_ela_level,equals,1,not_met,
2025,Miami,5,8,All,academic,1,n_failing_core,greater_than_or_equal,2,not_met,
2025,Newark,0,8,All,overall,1,is_off_track_attendance,equals,1,not_met,
2025,Newark,0,8,All,overall,1,is_off_track_academic,equals,1,not_met,
2025,Newark,5,8,All,overall,2,n_failing_core,greater_than_or_equal,2,not_met,
2025,Newark,9,12,All,overall,1,is_off_track_attendance,equals,1,not_met,
2025,Newark,9,12,All,overall,2,is_off_track_academic,equals,1,not_met,
2025,Camden,0,8,All,overall,1,is_off_track_attendance,equals,1,not_met,
2025,Camden,0,8,All,overall,1,is_off_track_academic,equals,1,not_met,
2025,Camden,5,8,All,overall,2,n_failing_core,greater_than_or_equal,2,not_met,
2025,Camden,9,12,All,overall,1,is_off_track_attendance,equals,1,not_met,
2025,Camden,9,12,All,overall,2,is_off_track_academic,equals,1,not_met,
2025,Miami,0,3,All,overall,1,is_off_track_attendance,equals,1,not_met,
2025,Miami,0,3,All,overall,2,is_off_track_academic,equals,1,not_met,
2025,Miami,4,4,All,overall,1,is_off_track_attendance,equals,1,not_met,
2025,Miami,4,4,All,overall,1,is_off_track_academic,equals,1,not_met,
2025,Miami,5,8,All,overall,1,is_off_track_attendance,equals,1,not_met,
2025,Miami,5,8,All,overall,2,is_off_track_academic,equals,1,not_met,
```

Transcription notes (why some rows look asymmetric — verified against the legacy
CASE logic):

- NJ K-8 ADA rules use `if_missing=met` (legacy: NULL ADA → Off-Track); Miami
  and all HS absence rules use `not_met` (legacy has no NULL clause there).
- Miami grade 3 has NO attendance rule in the legacy code (K; 1-2; 4; 5-8 only)
  — its attendance status becomes NULL, previously silent 'On-Track'.
- Legacy Miami has no HS; credit rules seeded for Newark/Camden only.
- NJ overall K-8 is attendance AND academic (one group, two pseudo rows); NJ HS
  and Miami non-grade-4 are OR (two groups); Miami grade 4 is AND.

- [ ] **Step 2: Hand off to the user**

Ask the user to: open the policies tab, delete the sample row, paste the CSV
contents (61 data rows), and confirm the named range
`src_google_sheets__reporting__promo_status_policies` still spans the data
(named ranges usually auto-expand; verify it covers all rows). Also ask them to
add sheet data-validation dropdowns on `region`, `term_name`, `domain`,
`metric`, `comparator`, and `if_missing` (per the spec) so leaders can't typo
the enums — the dbt tests are the backstop, not the first line of defense.

- [ ] **Step 3: Rebuild staging and re-run all policy tests** (sheets externals
      read live — no re-staging needed, but the staging TABLE must rebuild)

```bash
uv run dbt build \
  --select stg_google_sheets__reporting__promo_status_policies \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
uv run dbt test \
  --select stg_google_sheets__reporting__promo_status_policies+ \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

Expected: 61 rows; all error-severity tests pass; coverage test warns ONLY for
Miami grade 3 attendance (and Paterson grades if Paterson students exist in the
metrics model).

- [ ] **Step 4: Commit the scratch CSV? No** — `.claude/scratch/` is gitignored;
      nothing to commit. Proceed.

---

### Task 8: Diff validation against the legacy model

**Files:** none (BigQuery queries; findings noted in the PR body later).

**Context:** The legacy model still exists in prod
(`teamster-332318.kipptaf_reporting.int_reporting__promotional_status`). Compare
it to the dev build of the new model for `academic_year = 2025`. Run via
BigQuery MCP. Replace `{dev_schema}` with the dev students dataset (find it via
`uv run dbt show --inline "select '{{ target.schema }}'" --project-dir src/dbt/kipptaf --target dev`
then suffix `_students` per the custom schema; or read the build log's
fully-qualified name from Task 5 Step 4).

- [ ] **Step 1: Rebuild the new models against the seeded sheet**

```bash
uv run dbt build \
  --select int_students__promotional_status_metrics int_students__promotional_status \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

- [ ] **Step 2: Run the aggregate diff**

```sql
select
    lgcy.attendance_status as old_attendance,
    lgcy.academic_status as old_academic,
    lgcy.overall_status as old_overall,

    rebuilt.attendance_status as new_attendance,
    rebuilt.academic_status as new_academic,
    rebuilt.overall_status as new_overall,

    count(*) as n_rows,
from `teamster-332318`.kipptaf_reporting.int_reporting__promotional_status as lgcy
full join
    `teamster-332318`.{dev_schema}.int_students__promotional_status as rebuilt
    on lgcy.student_number = rebuilt.student_number
    and lgcy.academic_year = rebuilt.academic_year
    and lgcy.term_name = rebuilt.term_name
where coalesce(lgcy.academic_year, rebuilt.academic_year) = 2025
group by
    lgcy.attendance_status,
    lgcy.academic_status,
    lgcy.overall_status,
    rebuilt.attendance_status,
    rebuilt.academic_status,
    rebuilt.overall_status
```

Also run the same shape for `attendance_status_hs_detail`, `exemption`, and
`manual_retention`.

- [ ] **Step 3: Classify every mismatch cell**

Expected/acceptable differences (verified legacy quirks — everything else must
be investigated to root cause before proceeding):

1. **Miami grade 3 attendance**: legacy 'On-Track' (no rule, else-branch) → new
   NULL.
2. **Paterson students** (if any): legacy 'On-Track' everywhere (else-branch) →
   new NULL.
3. **Camden HS detail**: legacy `attendance_status_hs_detail` order checks
   `hs_at_risk_absences` (36) before `hs_off_track_absences` (9×term) so
   'Approaching' appears only below 36; new model reproduces this via group
   numbering — expect NO diff, but if one appears here, compare per-term
   thresholds first.
4. **NJ academic precedence bug**: legacy `academic_status` CASE for NJ 3-8 ends
   `... or c.n_failing_core >= 2`, which (operator precedence) fires for ANY
   region/grade — e.g. a Miami grade 2 student with 2+ core failures was
   legacy-Off-Track. The new model scopes `n_failing_core` to NJ 3-8 (and Miami
   5-8) only. Diffs matching this fingerprint (student outside NJ 3-8 / Miami
   5-8 with `n_failing_core >= 2`, old academic Off-Track, new On-Track) are the
   bug being fixed — count them and note the count in the PR body.
5. Students in year rows the sheet doesn't cover are excluded by the `= 2025`
   filter — prior years are NULL by design (backfill follow-up).

PII: inspect individual students locally only; the PR body gets aggregate
counts.

- [ ] **Step 4: Record results**

Write the classified diff summary (aggregate counts only) to
`.claude/scratch/promo-status-diff-summary.md` for use in the PR body.

---

### Task 9: Swap consumers and delete the legacy model

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__promo_status.sql:48`
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__promo_status.sql:131`
- Delete:
  `src/dbt/kipptaf/models/reporting/intermediate/int_reporting__promotional_status.sql`
- Delete:
  `src/dbt/kipptaf/models/reporting/intermediate/properties/int_reporting__promotional_status.yml`

**Interfaces:**

- Consumes: `ref("int_students__promotional_status")` (Task 5) — column names
  identical to legacy, so only the `ref()` strings change.

- [ ] **Step 1: Swap both refs**

In `rpt_tableau__promo_status.sql` (line ~48) and
`rpt_deanslist__promo_status.sql` (line ~131), change:

```sql
{{ ref("int_reporting__promotional_status") }}
```

to:

```sql
{{ ref("int_students__promotional_status") }}
```

(alias `as ps` / `as p` and every join condition stay unchanged).

- [ ] **Step 2: Delete the legacy model**

```bash
git rm src/dbt/kipptaf/models/reporting/intermediate/int_reporting__promotional_status.sql
git rm src/dbt/kipptaf/models/reporting/intermediate/properties/int_reporting__promotional_status.yml
```

- [ ] **Step 3: Build the consumers**

```bash
uv run dbt build \
  --select rpt_tableau__promo_status rpt_deanslist__promo_status \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

Expected: both views build; contract + uniqueness tests pass.

- [ ] **Step 4: Grep for stragglers**

```bash
grep -rn "int_reporting__promotional_status" /workspaces/teamster/src /workspaces/teamster/docs --include='*.sql' --include='*.yml' --include='*.md' | grep -v superpowers
```

Expected: no hits outside `docs/superpowers/` (spec/plan references are fine).

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor(kipptaf): point promo status consumers at policy engine, drop legacy model"
```

---

### Task 10: Final verification and PR

**Files:** none new.

- [ ] **Step 1: Full local build of the changed graph**

```bash
uv run dbt build --select state:modified+ \
  --project-dir src/dbt/kipptaf --target dev --defer --state target/prod
```

Expected: all models build, unit tests pass, error-severity tests pass.
Warn-level: coverage test warns for Miami grade 3 / Paterson only.

- [ ] **Step 2: Trunk check the changed files** (check-only linters fire at
      pre-push, not pre-commit — verify now)

```bash
git diff --name-only origin/main...HEAD | xargs /workspaces/teamster/.trunk/tools/trunk check --force
```

Expected: no issues. Fix anything reported (sqlfluff on models, yamllint on
properties, markdownlint on docs).

- [ ] **Step 3: Push and open the PR**

Push the branch. Open the PR with `mcp__github__create_pull_request` using
`.github/pull_request_template.md` as the body skeleton. Body must include:
`Closes #4324`, the design summary, the diff-validation aggregate summary from
`.claude/scratch/promo-status-diff-summary.md` (aggregates only — no student
identifiers), and the known behavior changes (Miami grade 3 / Paterson NULL
statuses; NJ precedence-bug fix with count). Note in the PR that
`stage_external_sources --target staging` was already run for the new source.
Avoid literal `<`/`>` tokens outside fenced blocks in the body (GitHub MCP
strips them) — spell comparators inside fenced blocks or as words. Read the
created PR body back to verify it wasn't mangled.

- [ ] **Step 4: Watch CI**

dbt Cloud CI is a commit status; Trunk/CodeQL/claude-review are check runs —
check both. After dbt Cloud CI passes, fetch warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` and confirm
nothing new beyond the expected coverage warns. Treat `claude-review` findings
as advisory — verify convention claims with `git grep` before complying.

- [ ] **Step 5: Post-merge handoffs (note in PR body)**

1. USER drops the orphaned prod view (a deleted model leaves its relation):
   `drop view if exists teamster-332318.kipptaf_reporting.int_reporting__promotional_status`
   (and the same relation in `zz_stg_kipptaf_reporting` if present).
2. Verify Dagster materializes the new sheet asset
   (`kipptaf/google/sheets/reporting/promo_status_policies`) and the new models
   after the location deploy (`get_location_load_history` →
   `get_asset_materializations`).
3. Open the follow-up issue for the 2-prior-year policy backfill (per #4324's
   Follow-up section), labels `feat`, `dbt`, `google-sheets`.

---

## Self-review notes

- **Spec coverage**: sheet source (Task 2), staging + structural tests (Task 3),
  metric catalog macro (Task 1), metrics model incl. string→int mappings and
  code-owned exemptions (Task 4), evaluation engine with two-pass
  pseudo-metrics, NULL semantics, detail labels, term scoping (Task 5),
  coverage + label-consistency tests (Tasks 3/6), seeding transcription (Task
  7), diff validation with known-diff whitelist (Task 8), consumer swap + legacy
  deletion (Task 9), rollout/CI/post-merge (Task 10). Backfill is explicitly out
  of scope (follow-up issue, Task 10 Step 5).
- **Type consistency**: policy `value` is float64; all metrics cast to float64
  before unpivot; pseudo-metrics cast bool→int→float64. Catalog names in Task 1
  = metrics-model columns in Task 4 = unpivot list in Task 5 = `metric` values
  in Task 7's CSV.
- **Known open risk**: dbt `unit_tests` `expect` with partial columns and
  `format: sql` fixtures — if dbt requires full-row expects, add the remaining
  output columns to the expect rows during Task 5 Step 3.
