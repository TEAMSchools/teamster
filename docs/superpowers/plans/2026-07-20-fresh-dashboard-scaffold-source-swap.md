# FRESH Dashboard Scaffold Source-Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the FRESH dashboard's hand-maintained Google Sheet scaffold
with a model that prefers PowerSchool-native data and falls back to the sheet
only where PowerSchool doesn't have it yet (or, for Miami, entirely — see Task
4), eliminate both hardcoded `2026` academic-year references, and ship a
reference doc + skill so this dashboard is maintainable by someone who's never
touched it.

**Architecture:** A new seam model (`int_finalsite__enrollment_scaffold`) blends
a PowerSchool-derived school×grade spine with the existing manual sheet,
controlled by one dbt var. A second new model
(`int_finalsite__current_academic_year`) derives "the current cycle" from
`status_crosswalk`, replacing two hardcoded `2026` literals. Downstream
consumers repoint to the new models with no contract changes.

**Tech Stack:** dbt (BigQuery), this repo's SQL/YAML conventions
(`src/dbt/CLAUDE.md`, `src/dbt/kipptaf/CLAUDE.md`).

## Global Constraints

- Design spec:
  [`docs/superpowers/specs/2026-07-20-fresh-dashboard-scaffold-source-swap-design.md`](2026-07-20-fresh-dashboard-scaffold-source-swap-design.md)
  — read it before starting; this plan implements it exactly, including the
  Miami carve-out and every verified caveat.
- All new/modified staging and intermediate models need a uniqueness test (repo
  convention, `src/dbt/CLAUDE.md`).
- SQL follows `.trunk/config/.sqlfluff` (trailing commas, no self-alias, ST06
  column ordering: plain columns grouped by source table first, then constants,
  then functions, then case statements). Don't hand-fix formatting — `trunk fmt`
  runs at commit time.
- No subqueries against tables/CTEs (this repo's convention) — every "current
  academic year" lookup is a `CROSS JOIN` against
  `int_finalsite__current_academic_year`, never a scalar subquery.
- Every task ends with
  `uv run dbt build --select <model> --target dev --defer --state <abs prod manifest path>`
  passing, per this repo's dev workflow (`src/dbt/CLAUDE.md` → "Dev `--defer`
  for unstaged externals"). Use the worktree-appropriate absolute `--state`
  path.
- Branch: `grangel/feat/claude-fresh-scaffold-swap`, already checked out (not a
  worktree — direct branch switch). Issue: #4451.

---

## Task 1: Guard the "one active crosswalk year" convention with a test

**Files:**

- Create:
  `src/dbt/kipptaf/tests/test_stg_google_sheets__finalsite__status_crosswalk_single_year.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`

**Interfaces:**

- Consumes: `stg_google_sheets__finalsite__status_crosswalk.file_year` (existing
  column).
- Produces: nothing consumed by later tasks — this is a standalone guard rail.
  Task 3's `int_finalsite__current_academic_year` relies on the invariant this
  test checks, but doesn't reference the test itself.

- [ ] **Step 1: Write the singular test**

`src/dbt/kipptaf/tests/test_stg_google_sheets__finalsite__status_crosswalk_single_year.sql`:

```sql
select count(distinct file_year) as distinct_file_years,
from {{ ref("stg_google_sheets__finalsite__status_crosswalk") }}
having count(distinct file_year) != 1
```

- [ ] **Step 2: Add the properties.yml entry**

Add to `src/dbt/kipptaf/tests/properties.yml` (append to the top-level
`data_tests:` list — do not create a second `data_tests:` key):

```yaml
- name: test_stg_google_sheets__finalsite__status_crosswalk_single_year
  description: >-
    status_crosswalk must hold config for exactly one academic year at a time (a
    documented convention, not an enforced constraint) --
    int_finalsite__current_academic_year derives "the current Finalsite cycle"
    via max(file_year), which silently returns NULL if the table is empty and
    silently favors the wrong year if two years' config accumulate. Both failure
    modes must fail loudly here instead.
  config:
    severity: error
    meta:
      dagster:
        ref:
          name: stg_google_sheets__finalsite__status_crosswalk
```

- [ ] **Step 3: Run the test against prod data (via `--defer`)**

Run:
`uv run dbt test --select test_stg_google_sheets__finalsite__status_crosswalk_single_year --target dev --defer --state <abs prod manifest path> --project-dir src/dbt/kipptaf`
Expected: PASS (today's data has exactly one row-set, `file_year = 2026`,
verified during design).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/tests/test_stg_google_sheets__finalsite__status_crosswalk_single_year.sql src/dbt/kipptaf/tests/properties.yml
git commit -m "test(dbt): guard status_crosswalk's single-active-year convention"
```

---

## Task 2: New model `int_finalsite__current_academic_year`

**Files:**

- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__current_academic_year.sql`
- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__current_academic_year.yml`

**Interfaces:**

- Consumes: `stg_google_sheets__finalsite__status_crosswalk.file_year`.
- Produces: a single-row model with one column, `academic_year` (`int64`). Every
  later task that previously depended on a hardcoded `2026` `CROSS JOIN`s this
  model and reads `academic_year` from it.

- [ ] **Step 1: Write the model**

`src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__current_academic_year.sql`:

```sql
select max(file_year) as academic_year,
from {{ ref("stg_google_sheets__finalsite__status_crosswalk") }}
```

- [ ] **Step 2: Write properties.yml**

`src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__current_academic_year.yml`:

```yaml
models:
  - name: int_finalsite__current_academic_year
    description: >
      Single-row model deriving the currently valid Finalsite academic year
      (start-year form, e.g. 2026 for AY2026-2027) from
      stg_google_sheets__finalsite__status_crosswalk's max(file_year) --
      status_crosswalk holds config for exactly one academic year at a time by
      convention (guarded by
      test_stg_google_sheets__finalsite__status_crosswalk_single_year). Raw
      Finalsite ingestion timing isn't a reliable signal for "the current year"
      since two academic years' student data can be live simultaneously with a
      non-standardized per-region rollover cadence -- status_crosswalk's
      single-active-year convention is the reliable anchor instead. Every model
      needing "the current Finalsite cycle" cross joins this model rather than
      hardcoding a year or reading a var.
    columns:
      - name: academic_year
        data_type: int64
        description: >
          The currently valid Finalsite academic year, in start-year form.
        data_tests:
          - not_null:
              config:
                severity: error
```

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select int_finalsite__current_academic_year --target dev --defer --state <abs prod manifest path> --project-dir src/dbt/kipptaf`
Expected: table built, 1 row, `academic_year = 2026`, `not_null` test passes.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__current_academic_year.sql src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__current_academic_year.yml
git commit -m "feat(dbt): add int_finalsite__current_academic_year"
```

---

## Task 3: New test — status ranking sync check

**Files:**

- Create:
  `src/dbt/kipptaf/tests/test_int_finalsite__status_order_matches_crosswalk_ranking.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`

**Interfaces:**

- Consumes: `int_finalsite__current_academic_year.academic_year` (Task 2),
  `stg_google_sheets__finalsite__status_crosswalk.{fs_status_field, detailed_status_ranking, file_year}`,
  `int_finalsite__status_report_unpivot.{fs_status_field, status_order}`
  (existing model).
- Produces: nothing consumed by later tasks — standalone guard rail.

- [ ] **Step 1: Write the singular test**

`src/dbt/kipptaf/tests/test_int_finalsite__status_order_matches_crosswalk_ranking.sql`:

**Important — do not compare against a live query of
`int_finalsite__status_report_unpivot`'s actual rows.** BigQuery's `UNPIVOT`
only emits a row for a source column when it's non-NULL for that row — a
`fs_status_field` that's declared in the hardcoded `CASE` but has never occurred
in the data (e.g. `retained_date`, if no student has ever had that status) never
appears in the model's output at all, producing a false mismatch against a
fully-populated crosswalk sheet. Compare against a **static list mirroring the
CASE's declaration** instead — immune to data occurrence, verified during
implementation (this exact false-positive was hit and fixed before landing):

```sql
with
    current_year as (
        select academic_year,
        from {{ ref("int_finalsite__current_academic_year") }}
    ),

    crosswalk_ranking as (
        select distinct
            x.fs_status_field,
            x.detailed_status_ranking,
        from {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
        inner join current_year as cy on x.file_year = cy.academic_year
    ),

    -- Mirrors the hardcoded status_order CASE in
    -- int_finalsite__status_report_unpivot.sql exactly.
    unpivot_order as (
        select fs_status_field, status_order,
        from
            unnest(
                [
                    struct('inquiry_date' as fs_status_field, 1 as status_order),
                    ('inquiry_completed_date', 2),
                    ('inactive_inquiry_date', 3),
                    ('applicant_date', 4),
                    ('application_withdrawn_date', 5),
                    ('deferred_date', 6),
                    ('application_complete_date', 7),
                    ('review_in_progress_date', 8),
                    ('waitlisted_date', 9),
                    ('denied_date', 10),
                    ('accepted_date', 11),
                    ('assigned_school_date', 12),
                    ('did_not_enroll_date', 13),
                    ('campus_transfer_requested_date', 14),
                    ('parent_declined_date', 15),
                    ('enrollment_in_progress_date', 16),
                    ('academic_hold_date', 17),
                    ('financial_hold_date', 18),
                    ('not_enrolling_date', 19),
                    ('enrolled_date', 20),
                    ('mid_year_withdrawal_date', 21),
                    ('never_attended_date', 22),
                    ('retained_date', 23),
                    ('summer_withdraw_date', 24)
                ]
            )
    )

select
    c.detailed_status_ranking,
    u.status_order,

    coalesce(c.fs_status_field, u.fs_status_field) as fs_status_field,

from crosswalk_ranking as c
full join unpivot_order as u on c.fs_status_field = u.fs_status_field
where
    c.detailed_status_ranking is null
    or u.status_order is null
    or c.detailed_status_ranking != u.status_order
```

If `int_finalsite__status_report_unpivot.sql`'s `status_order` `CASE` is ever
edited (a new status added, a ranking changed), this static list must be updated
to match by hand — it's a second place, alongside the sheet, that now needs to
stay in sync. Note this explicitly in a comment above the `CASE` in that file if
you touch it later.

- [ ] **Step 2: Add the properties.yml entry**

Append to `src/dbt/kipptaf/tests/properties.yml`:

```yaml
- name: test_int_finalsite__status_order_matches_crosswalk_ranking
  description: >-
    detailed_status_ranking (stg_google_sheets__finalsite__status_crosswalk,
    manually maintained) is hand-duplicated into a hardcoded CASE (status_order,
    int_finalsite__status_report_unpivot.sql) rather than joined live, per this
    repo's convention against staging-layer joins to Google Sheets sources.
    Nothing keeps the two in sync automatically -- editing the sheet's ranking
    (reordering, or adding a new status) doesn't update the hardcoded CASE, and
    a drift silently produces wrong same-day-tie tie-breaking in
    int_tableau__finalsite_student_scaffold's latest_status_calc with no error.
    This test fails loudly on any fs_status_field whose ranking differs between
    the two, or that's present in one but missing from the other, scoped to the
    current Finalsite academic year.
  config:
    severity: error
    meta:
      dagster:
        ref:
          name: int_finalsite__status_report_unpivot
```

- [ ] **Step 3: Run the test**

Run:
`uv run dbt test --select test_int_finalsite__status_order_matches_crosswalk_ranking --target dev --defer --state <abs prod manifest path> --project-dir src/dbt/kipptaf`
Expected: PASS (verified identical today during design, for every
`fs_status_field`, across both `enrollment_type` values).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/tests/test_int_finalsite__status_order_matches_crosswalk_ranking.sql src/dbt/kipptaf/tests/properties.yml
git commit -m "test(dbt): guard status_order / detailed_status_ranking sync"
```

---

## Task 4: New seam model `int_finalsite__enrollment_scaffold`

This is the core of the refactor. Read the design spec's "New seam model" and
"Deriving the current Finalsite academic year" sections before writing this —
the code below implements them exactly, including the Miami carve-out and the
`state_excludefromreporting` filter.

**Files:**

- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql`
- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__enrollment_scaffold.yml`
- Modify: `src/dbt/kipptaf/dbt_project.yml` (add the `finalsite_scaffold_source`
  var)

**Interfaces:**

- Consumes:
  `stg_powerschool__schools.{school_number, abbreviation, low_grade, high_grade, state_excludefromreporting, _dbt_source_project}`
  (existing),
  `stg_google_sheets__finalsite__school_scaffold.{academic_year, region, schoolid, school, grade_level, org, school_level}`
  (existing, unchanged), `int_finalsite__current_academic_year.academic_year`
  (Task 2), `extract_region()` macro (`kipptaf/macros/utils.sql`, existing).
- Produces:
  `academic_year, region, schoolid, school, grade_level, org, school_level, scaffold_source`
  (`'powerschool'` | `'gsheet'`), grain
  `(academic_year, region, schoolid, grade_level)`.

- [ ] **Step 1: Add the var to `dbt_project.yml`**

In `src/dbt/kipptaf/dbt_project.yml`, add to the top-level `vars:` block
(alongside the other kipptaf vars — do not create a second `vars:` key):

```yaml
finalsite_scaffold_source: blend # 'gsheet' | 'powerschool' | 'blend'
```

- [ ] **Step 2: Write the model**

`src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql`:

```sql
{% set scaffold_source_mode = var("finalsite_scaffold_source", "blend") %}

with
    current_year as (
        select academic_year,
        from {{ ref("int_finalsite__current_academic_year") }}
    ),

    powerschool_region as (
        select
            sps.school_number,
            sps.abbreviation,
            sps.low_grade,
            sps.high_grade,

            {{ extract_region("sps") }} as region,

        from {{ ref("stg_powerschool__schools") }} as sps
        where sps.state_excludefromreporting = 0
    ),

    -- Miami's SIS moved to Focus (#4441); stg_powerschool__schools' Miami
    -- rows are a frozen pre-migration snapshot, not a live source of truth.
    -- Deliberate, temporary carve-out -- confirmed with the team to keep
    -- Miami 100% sheet-sourced regardless of finalsite_scaffold_source
    -- until Focus is ready as a scaffold source. Remove this filter (and
    -- update the sheet-side builder's Miami note below) once that happens.
    powerschool_schools as (
        select school_number, abbreviation, low_grade, high_grade, region,
        from powerschool_region
        where region != 'Miami'
    ),

    grade_expansion as (
        select
            school_number,
            abbreviation,
            region,

            grade_level,

        from powerschool_schools
        cross join unnest(generate_array(low_grade, high_grade)) as grade_level
    ),

    -- No grade_level = -1 row is synthesized here. PowerSchool's own
    -- grade-level domain uses negative values for a different, real
    -- meaning (pre-registration / pre-K context) -- the scaffold's
    -- grade_level = -1 "whole school total" sentinel must never be
    -- conflated with that. The -1 row always comes from gsheet_scaffold
    -- below.
    powerschool_scaffold as (
        select
            ge.school_number as schoolid,
            ge.abbreviation as school,
            ge.region,
            ge.grade_level,

            cy.academic_year,

            'KTAF' as org,
            'powerschool' as scaffold_source,

            case
                when ge.grade_level >= 9
                then 'HS'
                when ge.grade_level >= 5
                then 'MS'
                when ge.grade_level >= 0
                then 'ES'
            end as school_level,

        from grade_expansion as ge
        cross join current_year as cy
    )

    {% if scaffold_source_mode in ("gsheet", "blend") %}
    ,

    -- Scoped to the current cycle so a stale row from a prior year (a
    -- closed school, a dropped grade) doesn't look identical to "PS
    -- doesn't have this yet" and get silently resurrected forever. Miami
    -- must carry its FULL spine here (every school, every grade), not just
    -- -1 rows and net-new entries, since the PowerSchool builder excludes
    -- it entirely above.
    gsheet_scaffold as (
        select
            s.schoolid,
            s.school,
            s.region,
            s.grade_level,
            s.academic_year,
            s.org,
            s.school_level,

            'gsheet' as scaffold_source,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
        inner join current_year as cy on s.academic_year = cy.academic_year
    )
    {% endif %}

{% if scaffold_source_mode == "powerschool" %}

select schoolid, school, region, grade_level, academic_year, org, scaffold_source, school_level,
from powerschool_scaffold

{% elif scaffold_source_mode == "gsheet" %}

select schoolid, school, region, grade_level, academic_year, org, scaffold_source, school_level,
from gsheet_scaffold

{% else %}

select schoolid, school, region, grade_level, academic_year, org, scaffold_source, school_level,
from powerschool_scaffold

union all

select
    g.schoolid, g.school, g.region, g.grade_level, g.academic_year, g.org, g.scaffold_source, g.school_level,
from gsheet_scaffold as g
left join
    powerschool_scaffold as p
    on g.schoolid = p.schoolid
    and g.grade_level = p.grade_level
where p.schoolid is null

{% endif %}
```

- [ ] **Step 3: Write properties.yml**

`src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__enrollment_scaffold.yml`:

```yaml
models:
  - name: int_finalsite__enrollment_scaffold
    description: >
      School x grade spine for the FRESH dashboard, replacing the fully
      hand-maintained stg_google_sheets__finalsite__school_scaffold. Source is
      controlled by var finalsite_scaffold_source ('gsheet' | 'powerschool' |
      'blend', default 'blend'): the PowerSchool builder derives grade spans
      from stg_powerschool__schools (grade-span expansion, not enrollment
      actuals, so an empty-but-recruited grade still appears); the sheet builder
      covers what PowerSchool can't -- every school's grade_level = -1
      whole-school row (PowerSchool never supplies this; see the school_level
      note on that column), genuinely new schools/grades not yet live in
      PowerSchool, and all of Miami (deliberate, temporary carve-out -- Miami's
      SIS moved to Focus and Focus isn't ready as a scaffold source yet). In
      blend mode, PowerSchool wins on any overlapping (schoolid, grade_level)
      key; the sheet fills everything else -- the same single rule naturally
      covers -1 rows, genuinely-new grades/schools, and the entire Miami region,
      with no special-casing.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - academic_year
              - region
              - schoolid
              - grade_level
          config:
            severity: error
    columns:
      - name: academic_year
        data_type: int64
        description: >
          The current Finalsite recruitment cycle -- always
          int_finalsite__current_academic_year's value, never a historical year
          (stg_powerschool__schools is current-state only).
      - name: region
        data_type: string
        description: One of "Newark", "Camden", "Miami", "Paterson".
      - name: schoolid
        data_type: int64
        description: PowerSchool school_number.
      - name: school
        data_type: string
        description: Short school abbreviation (e.g. "KURA", "Legacy ES").
      - name: grade_level
        data_type: int64
        description: >
          -1 = whole-school total row (never PowerSchool-sourced -- see
          scaffold_source), else 0-12.
      - name: org
        data_type: string
        description: Always "KTAF" (verified constant, network-wide).
      - name: school_level
        data_type: string
        description: >
          ES / MS / HS. On PowerSchool-sourced rows, derived per expanded
          grade_level (>=9 HS, >=5 MS, >=0 ES) -- NOT read from
          stg_powerschool__schools.school_level, which is a single per-school
          value and would incorrectly apply one classification to a school
          spanning two bands. On gsheet-sourced rows, whatever the analyst
          entered.
      - name: scaffold_source
        data_type: string
        description: >
          'powerschool' or 'gsheet' -- per-row lineage tag, not a mode-level
          constant. In blend mode a given row is tagged with whichever builder
          actually produced it.
```

- [ ] **Step 4: Build and verify**

Run:
`uv run dbt build --select int_finalsite__enrollment_scaffold --target dev --defer --state <abs prod manifest path> --project-dir src/dbt/kipptaf`
Expected: table built, uniqueness test passes. Then manually spot-check via
BigQuery MCP or `dbt show`:

- Every row has `region != 'Miami'` where `scaffold_source = 'powerschool'`.
- Miami rows are 100% `scaffold_source = 'gsheet'`.
- No row has `grade_level = -1` and `scaffold_source = 'powerschool'`.
- Sumner (Camden) grades 5/6 show `school_level = 'MS'`, grades 0-4 show `'ES'`
  -- confirms the per-grade CASE handles this correctly with no override needed
  (verified during design; do not add override logic here).

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__enrollment_scaffold.yml src/dbt/kipptaf/dbt_project.yml
git commit -m "feat(dbt): add int_finalsite__enrollment_scaffold seam model"
```

---

## Task 5: Rename `int_google_sheets__finalsite__scaffold` to `int_finalsite__goals_scaffold`

**Files:**

- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__goals_scaffold.sql`
- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__goals_scaffold.yml`
- Delete:
  `src/dbt/kipptaf/models/google/sheets/intermediate/int_google_sheets__finalsite__scaffold.sql`
- Delete:
  `src/dbt/kipptaf/models/google/sheets/intermediate/properties/int_google_sheets__finalsite__scaffold.yml`

**Interfaces:**

- Consumes: `int_finalsite__enrollment_scaffold` (Task 4, replaces the old
  `stg_google_sheets__finalsite__school_scaffold` ref),
  `stg_google_sheets__finalsite__goals` (existing, unchanged).
- Produces: same contract as the old model
  (`academic_year, org, region, schoolid, school, grade_level, school_level, goal_granularity, goal_type, goal_name, goal_value, grouped_status_timeframe`)
  — Task 6 (`rpt_tableau__fresh_dashboard_aggregated`) repoints its `ref()` to
  this new name.

- [ ] **Step 1: Read the current model's exact SQL before moving it**

Run:
`cat src/dbt/kipptaf/models/google/sheets/intermediate/int_google_sheets__finalsite__scaffold.sql`
(Already known from the design spec's Context section — the join logic is
unchanged, only the `ref()` for the scaffold side changes.)

- [ ] **Step 2: Write the moved/renamed model**

`src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__goals_scaffold.sql`:

```sql
select
    b.academic_year,
    b.org,
    b.region,
    b.schoolid,
    b.school,
    b.grade_level,

    g.school_level,
    g.goal_granularity,
    g.goal_type,
    g.goal_name,
    g.goal_value,

    case
        when
            g.goal_type in (
                'Inquiries',
                'Applications',
                'Offers',
                'Assigned School',
                'Accepted',
                'Conversion'
            )
        then 'Ever'
        else 'Current'
    end as grouped_status_timeframe,

from {{ ref("int_finalsite__enrollment_scaffold") }} as b
inner join
    {{ ref("stg_google_sheets__finalsite__goals") }} as g
    on b.academic_year = g.enrollment_academic_year
    and b.region = g.region
    and b.schoolid = g.schoolid
    and b.grade_level = g.grade_level
where g.goal_type != 'Enrollment'
```

- [ ] **Step 3: Write properties.yml**

Copy the column-level `data_tests`/`description` content from the deleted file's
properties.yml verbatim into
`src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__goals_scaffold.yml`,
updating only the top-level `name:` to `int_finalsite__goals_scaffold`. Read the
old properties file first (Step 1 output side-effect) to get its exact current
content — don't guess at columns/tests that may already exist there.

- [ ] **Step 4: Delete the old files**

```bash
git rm src/dbt/kipptaf/models/google/sheets/intermediate/int_google_sheets__finalsite__scaffold.sql src/dbt/kipptaf/models/google/sheets/intermediate/properties/int_google_sheets__finalsite__scaffold.yml
```

- [ ] **Step 5: Build and verify**

Run:
`uv run dbt build --select int_finalsite__goals_scaffold --target dev --defer --state <abs prod manifest path> --project-dir src/dbt/kipptaf`
Expected: builds cleanly, all carried-over tests pass, row count roughly matches
the old model's (compare via `dbt show` or BigQuery MCP against the prod
`int_google_sheets__finalsite__scaffold` table before it's removed from prod).

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__goals_scaffold.sql src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__goals_scaffold.yml
git commit -m "refactor(dbt): rename int_google_sheets__finalsite__scaffold to int_finalsite__goals_scaffold"
```

---

## Task 6: Repoint `rpt_tableau__fresh_dashboard_aggregated`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_aggregated.sql`

**Interfaces:**

- Consumes: `int_finalsite__goals_scaffold` (Task 5).
- Produces: no contract/column change — `ref()` rename only.

- [ ] **Step 1: Update the ref**

In
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_aggregated.sql`,
every occurrence of

```sql
from {{ ref("int_google_sheets__finalsite__scaffold") }} as s
```

becomes

```sql
from {{ ref("int_finalsite__goals_scaffold") }} as s
```

(There are 5 occurrences, one per `union all` branch — replace all of them. No
other line in this file changes.)

- [ ] **Step 2: Build and verify**

Run:
`uv run dbt build --select rpt_tableau__fresh_dashboard_aggregated --target dev --defer --state <abs prod manifest path> --project-dir src/dbt/kipptaf`
Expected: builds cleanly with no logic change — compare row count and a sample
of `goal_value` sums against the current prod table (BigQuery MCP) to confirm no
behavior drift from the rename alone.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_aggregated.sql
git commit -m "refactor(dbt): repoint rpt_tableau__fresh_dashboard_aggregated to int_finalsite__goals_scaffold"
```

---

## Task 7: Fix the hardcoded year in `int_tableau__finalsite_student_scaffold`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__finalsite_student_scaffold.sql`

**Interfaces:**

- Consumes: `int_finalsite__current_academic_year.academic_year` (Task 2).
- Produces: no contract change — replaces a hardcoded filter value.

- [ ] **Step 1: Add the cross join and replace the hardcoded year**

In the `latest_status_calc` CTE, add a new CTE above it and change the `WHERE`
clause:

```sql
with
    current_year as (
        select academic_year,
        from {{ ref("int_finalsite__current_academic_year") }}
    ),

    latest_status_calc as (
        select
            r.enrollment_academic_year,
            r.enrollment_academic_year_display,
            r.org,
            r.region,
            r.schoolid,
            r.finalsite_enrollment_id as finalsite_id,
            r.powerschool_student_number,
            r.first_name,
            r.last_name,
            r.grade_level,
            r.enrollment_type,
            r.self_contained,
            r.gender,
            r.birthdate,
            r.detailed_status,
            r.status_start_date,
            r.status_order,

            x.status_group_name,
            x.status_group_value,
            x.grouped_status_order,
            x.grouped_status_timeframe,

            'All' as aligned_enrollment_type,

            if(
                x.status_group_value in ('Inquiries', 'Applications'),
                r.region,
                r.school
            ) as school,

            first_value(r.detailed_status) over (
                partition by r.finalsite_enrollment_id
                order by r.status_start_date desc, r.status_order desc
            ) as latest_status,

        from {{ ref("int_finalsite__status_report_unpivot") }} as r
        cross join current_year as cy
        inner join
            {{ ref("int_google_sheets__finalsite__status_crosswalk_unpivot") }} as x
            on r._dagster_partition_key = x._dagster_partition_key
            and r.enrollment_type = x.enrollment_type
            and r.detailed_status = x.detailed_status
            and x.valid_detailed_status
            and not x.qa_flag
        where r.enrollment_academic_year = cy.academic_year
    ),
```

Every other CTE in this file (`start_dates`, `deduplicate`, `roster`,
`add_group_status_end_date`, `days_in_grouped_status_calc`,
`filter_days_in_status`, `enrollment_lookup`, `deduplicate_enrollments`,
`final_roster`, and the final `select`) is **unchanged** — this is the only
hardcoded-year fix in this file, per the design spec's Non-goals (no other
status/goal-type logic changes here).

- [ ] **Step 2: Build and verify**

Run:
`uv run dbt build --select int_tableau__finalsite_student_scaffold --target dev --defer --state <abs prod manifest path> --project-dir src/dbt/kipptaf`
Expected: builds cleanly, row count matches current prod (BigQuery MCP
comparison) since `academic_year = 2026` is what
`int_finalsite__current_academic_year` resolves to today — this is a
behavior-preserving change today, only differing in future years.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__finalsite_student_scaffold.sql
git commit -m "fix(dbt): derive the current academic year in int_tableau__finalsite_student_scaffold instead of hardcoding 2026"
```

---

## Task 8: Repoint and fix `rpt_tableau__fresh_dashboard_progress_to_goals`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_progress_to_goals.sql`

**Interfaces:**

- Consumes: `int_finalsite__enrollment_scaffold` (Task 4, replaces
  `stg_google_sheets__finalsite__school_scaffold`),
  `int_finalsite__current_academic_year.academic_year` (Task 2, replaces two
  hardcoded `2026` literals).
- Produces: no contract change.

- [ ] **Step 1: Repoint the `scaffold` CTE and add the year cross join**

At the top of the file, change:

```sql
with
    scaffold as (
        /* dont have a better location where only one schoolid matches a single school
           name */
        select distinct
            s.academic_year,
            s.org,
            s.region,
            s.schoolid,
            s.school,
            s.grade_level,

            x.location_grade_band as school_level,

            enrollment_type,

            'School' as goal_granularity,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
        left join
            {{ ref("int_people__location_crosswalk") }} as x
            on s.schoolid = x.location_powerschool_school_id
        cross join unnest(['All', 'New', 'Returning']) as enrollment_type
        where s.grade_level = -1

        union all

        /* dont have a better location where only one schoolid matches a single school
           name */
        select distinct
            s.academic_year,
            s.org,
            s.region,
            s.schoolid,
            s.school,
            s.grade_level,

            s.school_level,

            enrollment_type,

            'School/Grade Level' as goal_granularity,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
        cross join unnest(['All', 'New', 'Returning']) as enrollment_type
        where s.grade_level != -1 and s.schoolid != 0
    ),
```

to (note: no `current_year` CTE is introduced here — per this repo's
no-pass-through-CTE convention, applied consistently with Task 4's checkpoint
fix, `int_finalsite__current_academic_year` is cross-joined directly at each of
the two usage sites in Step 2, not wrapped in a shared CTE at the top of the
file):

```sql
with
    scaffold as (
        /* dont have a better location where only one schoolid matches a single school
           name */
        select distinct
            s.academic_year,
            s.org,
            s.region,
            s.schoolid,
            s.school,
            s.grade_level,

            x.location_grade_band as school_level,

            enrollment_type,

            'School' as goal_granularity,

        from {{ ref("int_finalsite__enrollment_scaffold") }} as s
        left join
            {{ ref("int_people__location_crosswalk") }} as x
            on s.schoolid = x.location_powerschool_school_id
        cross join unnest(['All', 'New', 'Returning']) as enrollment_type
        where s.grade_level = -1

        union all

        /* dont have a better location where only one schoolid matches a single school
           name */
        select distinct
            s.academic_year,
            s.org,
            s.region,
            s.schoolid,
            s.school,
            s.grade_level,

            s.school_level,

            enrollment_type,

            'School/Grade Level' as goal_granularity,

        from {{ ref("int_finalsite__enrollment_scaffold") }} as s
        cross join unnest(['All', 'New', 'Returning']) as enrollment_type
        where s.grade_level != -1 and s.schoolid != 0
    ),
```

- [ ] **Step 2: Replace the two hardcoded `2026` filters**

**Important — adding the cross join makes every other column reference in this
`select` ambiguous** (sqlfluff RF02 fires: "unqualified reference found in
select with more than one referenced table/view") once a second table
(`int_finalsite__current_academic_year`) is in the `FROM`/`JOIN` — so every
plain column from `int_google_sheets__finalsite__goals_pivot` must be qualified
with an alias, not just the filter predicates. **Also — do not reorder any of
the qualified columns relative to the other two branches in this `UNION ALL`.**
`BigQuery` matches `UNION ALL` columns **positionally, not by name**; moving
`grade_level` to sit next to the other plain columns (the natural ST06 instinct)
breaks positional alignment against the PART 1A/1B branches above, which keep
`finalsite_id` at position 5 and `grade_level` at position 9 — this exact
mistake was made and caught via a real `dbt build` failure ("Column 5 in UNION
ALL has incompatible types") during implementation. Keep `grade_level` in its
original position, after the four `null as ...` columns, exactly as shown below.

In the `data_stack_school` CTE, change:

```sql
        -- PART 2: THE GOALS (Targets) - School
        select
            enrollment_academic_year,
            region,
            schoolid,
            school,

            null as finalsite_id,
            null as powerschool_student_number,
            null as first_name,
            null as last_name,
            grade_level,

            'Goal Record' as latest_status,
            'NA' as self_contained,
            null as enroll_status,
            null as is_enrolled_fdos,
            null as is_enrolled_oct01,
            null as is_enrolled_oct15,
            null as is_enrolled_mar15,

            'Goal' as row_type,

            0 as student_count,

            seat_target,
            fdos_target,
            budget_target,
            new_student_target,
            re_enroll_projection,

            enrollment_type,

        from {{ ref("int_google_sheets__finalsite__goals_pivot") }}
        where
            goal_granularity = 'School'
            and goal_type = 'Enrollment'
            and enrollment_academic_year = 2026
    ),
```

to:

```sql
        -- PART 2: THE GOALS (Targets) - School
        select
            gp.enrollment_academic_year,
            gp.region,
            gp.schoolid,
            gp.school,

            null as finalsite_id,
            null as powerschool_student_number,
            null as first_name,
            null as last_name,
            gp.grade_level,

            'Goal Record' as latest_status,
            'NA' as self_contained,
            null as enroll_status,
            null as is_enrolled_fdos,
            null as is_enrolled_oct01,
            null as is_enrolled_oct15,
            null as is_enrolled_mar15,

            'Goal' as row_type,

            0 as student_count,

            gp.seat_target,
            gp.fdos_target,
            gp.budget_target,
            gp.new_student_target,
            gp.re_enroll_projection,

            gp.enrollment_type,

        from {{ ref("int_google_sheets__finalsite__goals_pivot") }} as gp
        cross join {{ ref("int_finalsite__current_academic_year") }} as cy
        where
            gp.goal_granularity = 'School'
            and gp.goal_type = 'Enrollment'
            and gp.enrollment_academic_year = cy.academic_year
    ),
```

Apply the identical transformation (add the `gp` alias, qualify every column,
add the `cross join`, keep `grade_level`'s position unchanged) to
`data_stack_school_grade`'s PART 2 block, whose only difference is
`goal_granularity = 'School/Grade Level'` in the filter.

- [ ] **Step 3: Build and verify**

Run:
`uv run dbt build --select rpt_tableau__fresh_dashboard_progress_to_goals --target dev --defer --state <abs prod manifest path> --project-dir src/dbt/kipptaf`
Expected: builds cleanly. Compare row counts and a sample of goal values per
school against current prod (BigQuery MCP) — should match exactly today, since
both the scaffold swap (in `blend` mode) and the year derivation resolve to the
same values as before for AY2026.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_progress_to_goals.sql
git commit -m "refactor(dbt): repoint fresh_dashboard_progress_to_goals to the new scaffold and derived academic year"
```

---

## Task 9: Update the `fresh_dashboard` exposure

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml`

**Interfaces:**

- Consumes: nothing new — updates `depends_on` refs to match renamed models.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Update `depends_on`**

In `src/dbt/kipptaf/models/exposures/tableau.yml`, the `fresh_dashboard`
exposure's `depends_on` list stays functionally the same (it lists the two
`rpt_` models and `int_tableau__finalsite_student_scaffold`, none of which were
renamed) — confirm no entry references `int_google_sheets__finalsite__scaffold`
or `stg_google_sheets__finalsite__school_scaffold` directly. If either does,
update it to `int_finalsite__goals_scaffold` /
`int_finalsite__enrollment_scaffold` respectively.

- [ ] **Step 2: Parse-check**

Run: `uv run dbt parse --project-dir src/dbt/kipptaf --target dev` Expected: no
errors — confirms every `ref()` in the exposure resolves.

- [ ] **Step 3: Commit (only if Step 1 required a change)**

```bash
git add src/dbt/kipptaf/models/exposures/tableau.yml
git commit -m "chore(dbt): update fresh_dashboard exposure refs"
```

---

## Task 10: Goal definitions in YAML

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__finalsite__goals.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/intermediate/properties/int_google_sheets__finalsite__goals_pivot.yml`

**Interfaces:**

- Consumes: nothing — pure documentation addition, no SQL changes.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add column descriptions to the goals staging model**

In `stg_google_sheets__finalsite__goals.yml`, add `description:` fields to
`goal_type` and `goal_name` (the columns don't need per-value descriptions in
the contract yml itself — put the full definitions in the reference doc, Task 11
— but add a short pointer here per this repo's convention that yml is the
analyst-facing documentation mechanism):

```yaml
models:
  - name: stg_google_sheets__finalsite__goals
    columns:
      - name: enrollment_academic_year
        data_type: int64
      - name: region
        data_type: string
      - name: school_level
        data_type: string
      - name: schoolid
        data_type: int64
      - name: school
        data_type: string
      - name: grade_level
        data_type: int64
      - name: goal_granularity
        data_type: string
        description: >
          "School" (whole-school total, grade_level = -1), "School/Grade Level",
          or "Region/Grade Level" (Inquiries/Applications/Deferred/ Waitlisted
          -- not tied to a specific school).
      - name: goal_type
        data_type: string
        description: >
          "Enrollment" goals (Seat Target, FDOS Target, New Student Target,
          Budget Target, Re-Enroll Projection) are plain manually-entered
          targets. Every other goal_type is a computed roll-up of the Finalsite
          recruitment funnel via status_crosswalk -- see
          docs/reference/fresh-dashboard-data-model.md for full definitions.
      - name: goal_name
        data_type: string
        description: >
          See docs/reference/fresh-dashboard-data-model.md for the full
          goal_name glossary (Seat Target, FDOS Target, New Student Target,
          Budget Target, Re-Enroll Projection, Inquiries, App Target, Offers
          Target, Accepted, Waitlisted, Deferred, Enrollment In Progress,
          Pending Offers [+ day-bucket splits], Conversion sub-types).
      - name: goal_value
        data_type: numeric
```

- [ ] **Step 2: Add matching descriptions to the pivoted columns**

Read `int_google_sheets__finalsite__goals_pivot.yml` first to see its current
column list, then add a one-line `description:` to each pivoted column
(`seat_target`, `fdos_target`, `budget_target`, `new_student_target`,
`re_enroll_projection`) matching the definitions below (from the design spec):

- `seat_target`: Total seats/capacity the school is targeting for the year.
- `fdos_target`: Enrollment target as of First Day of School.
- `budget_target`: The enrollment number the school's budget was built against.
- `new_student_target`: Target count of new (not returning) students to enroll.
- `re_enroll_projection`: Projected count of currently-enrolled students
  expected to persist (return) -- "persistence," not "retention"; retention
  refers to grade repetition in this org's vocabulary and is a distinct,
  unrelated concept.

- [ ] **Step 3: Parse-check**

Run: `uv run dbt parse --project-dir src/dbt/kipptaf --target dev` Expected: no
errors (yml-only change, but confirms no syntax break).

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__finalsite__goals.yml src/dbt/kipptaf/models/google/sheets/intermediate/properties/int_google_sheets__finalsite__goals_pivot.yml
git commit -m "docs(dbt): add goal definitions to finalsite goals yml"
```

---

## Task 11: Reference doc `docs/reference/fresh-dashboard-data-model.md`

**Files:**

- Create: `docs/reference/fresh-dashboard-data-model.md`
- Modify: `mkdocs.yml`

**Interfaces:**

- Consumes: nothing — pure documentation.
- Produces: linked from Task 12's skill.

- [ ] **Step 1: Write the reference doc**

`docs/reference/fresh-dashboard-data-model.md` — write this exact content
(adapted for a doc's tone from the design spec, not copy-pasted verbatim — the
spec keeps its process/history framing; this doc states the model as it works,
permanently):

````markdown
# FRESH Dashboard Data Model

## What is FRESH?

FRESH is the network's enrollment recruitment dashboard: it tracks progress
against recruitment targets (seats, new students, application/offer/ enrollment
funnel counts) broken out by region, school, and grade. It has two Tableau views
— **Progress to Goals** (`rpt_tableau__fresh_dashboard_progress_to_goals`) and
**Aggregated** (`rpt_tableau__fresh_dashboard_aggregated`) — both built from the
same underlying scaffold and goals data.

## Data model overview

```text
stg_powerschool__schools ─┐
                          ├─▶ int_finalsite__enrollment_scaffold ─┬─▶ rpt_tableau__fresh_dashboard_progress_to_goals
stg_google_sheets__finalsite__school_scaffold ─┘                  │
                                                                    └─▶ int_finalsite__goals_scaffold ─▶ rpt_tableau__fresh_dashboard_aggregated
                                                                          ▲
stg_google_sheets__finalsite__goals ─────────────────────────────────────┘

stg_finalsite__status_report ─▶ int_finalsite__status_report_unpivot ─┐
                                                                        ├─▶ int_tableau__finalsite_student_scaffold ─▶ both rpt_ models above
stg_google_sheets__finalsite__status_crosswalk ─▶ int_google_sheets__finalsite__status_crosswalk_unpivot ─┘

stg_google_sheets__finalsite__status_crosswalk ─▶ int_finalsite__current_academic_year ─▶ (cross-joined by every model above needing "the current cycle")
```

The **scaffold** (school × grade spine) and the **goals** (numeric targets) are
two independent inputs that get joined together. The **actuals** (where students
actually are in the recruitment funnel) come from a completely separate
Finalsite pipeline, joined in downstream.

## The scaffold: `int_finalsite__enrollment_scaffold`

This model produces one row per `(academic_year, region, schoolid, grade_level)`
— the spine everything else joins against. It replaced a fully hand-maintained
Google Sheet with a model that prefers PowerSchool-native data and falls back to
the sheet only where PowerSchool doesn't have it.

**Two builders, blended:**

- **PowerSchool builder** — expands each school's `low_grade`–`high_grade` span
  (`stg_powerschool__schools`) into one row per grade. This exists whether or
  not any student is currently enrolled in a given grade, which is exactly
  what's needed for a grade actively being recruited into (an actuals-based
  approach wouldn't show an empty-but-recruited grade at all). Filtered to
  `state_excludefromreporting = 0` first — `stg_powerschool__schools` includes
  non-reporting/administrative rows (e.g. the `999999` "Graduated Students"
  sentinel) that would otherwise produce garbage scaffold rows.
- **Sheet builder** — `stg_google_sheets__finalsite__school_scaffold`, filtered
  to the current academic year (via `int_finalsite__current_academic_year`, so a
  stale row from a prior, closed cycle can never look like "PowerSchool doesn't
  have this yet"). Supplies what PowerSchool structurally can't: every school's
  `grade_level = -1` whole-school-total row, and genuinely new schools/grades
  not yet live in PowerSchool.

**Important: `grade_level = -1` means "whole-school total row" in this
scaffold's convention** — a reporting convenience, not a PowerSchool concept.
PowerSchool's own grade-level domain uses negative values for a different, real
meaning (pre-registration/pre-K). The PowerSchool builder never synthesizes a
`-1` row — it's always sheet-sourced, by design, regardless of what
`low_grade`/`high_grade` contain in any given year.

**Miami carve-out (deliberate and temporary):** Miami is excluded from the
PowerSchool builder entirely, unconditionally, regardless of the
`finalsite_scaffold_source` var. Miami's SIS moved to Focus
(`src/dbt/powerschool/CLAUDE.md`, #4441) and no longer consumes the PowerSchool
package — `stg_powerschool__schools`'s Miami rows are a frozen pre-migration
snapshot, not a live source of truth. Some actively-recruited Miami schools
(Legacy ES, Legacy MS, MTH as of AY2026) were never onboarded to PowerSchool
post-migration at all — a permanent gap, not a transitional one PowerSchool
coverage will ever close on its own. Confirmed with the team: Miami stays 100%
sheet-sourced (a full spine — every school, every grade, not just `-1` rows and
net-new entries) until Focus is ready as a scaffold source and this is
revisited.

**Source-selection control** — one dbt var, `finalsite_scaffold_source`
(`kipptaf/dbt_project.yml`), default `blend`:

| Value             | Behavior                                                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `gsheet`          | Sheet builder only.                                                                                                                  |
| `powerschool`     | PowerSchool builder only. Never produces `-1` rows on its own.                                                                       |
| `blend` (default) | PowerSchool builder, plus sheet rows whose `(schoolid, grade_level)` key is absent from it. PowerSchool wins on any overlapping key. |

Because the PowerSchool builder never emits a `-1` row and never covers Miami,
`blend`'s single rule ("PowerSchool wins on any overlapping key; sheet fills the
rest") naturally and correctly handles `-1` rows, genuinely-new grades/schools,
and all of Miami — no special-casing needed for any of them.

## The current academic year: `int_finalsite__current_academic_year`

A single-row model:
`select max(file_year) as academic_year from stg_google_sheets__finalsite__status_crosswalk`.
Every model needing "the current Finalsite cycle" cross joins this instead of
hardcoding a year.

Why not derive it from raw Finalsite ingestion instead? Finalsite can carry
**two concurrent academic years of live student data at once** during a
transition period — individual students and regions roll over on their own
uncoordinated timeline, with no standardized cadence. So "which year has the
newest raw data" isn't reliable. `status_crosswalk` holds config for **exactly
one academic year at a time** by convention (guarded by
`test_stg_google_sheets__finalsite__status_crosswalk_single_year`), which is the
reliable signal instead.

## Goal definitions

The `Enrollment` goal_type group is **not** computed via `status_crosswalk` at
all — plain numeric targets entered directly on the goals sheet:

| `goal_name`            | Definition                                                                                                                                                                                                        |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Seat Target`          | Total seats/capacity the school is targeting for the year.                                                                                                                                                        |
| `FDOS Target`          | Enrollment target as of First Day of School.                                                                                                                                                                      |
| `New Student Target`   | Target count of new (not returning) students to enroll.                                                                                                                                                           |
| `Budget Target`        | The enrollment number the school's budget was built against.                                                                                                                                                      |
| `Re-Enroll Projection` | Projected count of currently-enrolled students expected to persist (return) — "persistence," not "retention"; retention refers to grade repetition in this org's vocabulary and is a distinct, unrelated concept. |

Everything else is a computed roll-up of the Finalsite recruitment funnel via
`status_crosswalk`'s `status_group_value` mapping and `grouped_status_timeframe`
(`Ever` = cumulative, counts a student who ever reached this status even if they
later moved past or reversed; `Current` = point-in-time, latest status only):

| `goal_name` (`goal_type`)                                                           | Timeframe | Definition                                                                                                                      |
| ----------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `Inquiries`                                                                         | Ever      | Family ever submitted an inquiry.                                                                                               |
| `App Target` (`Applications`)                                                       | Ever      | Family ever completed/submitted an application.                                                                                 |
| `Offers Target` (`Offers`)                                                          | Ever      | Student was ever offered a seat.                                                                                                |
| `Accepted`                                                                          | Ever      | Family ever accepted an offered seat.                                                                                           |
| `Waitlisted`                                                                        | Current   | Student's current status is waitlisted.                                                                                         |
| `Deferred`                                                                          | Current   | Student's current status is deferred.                                                                                           |
| `Enrollment In Progress`                                                            | Current   | Student is currently mid-enrollment paperwork/process.                                                                          |
| `Pending Offers` (+ `<= 4 Days` / `>= 5 & <= 10 Days` / `> 10 Days`)                | Current   | Student has an outstanding offer awaiting a family response, bucketed by days pending — an SLA/staleness tracker for follow-up. |
| `Conversion` — `Accepted to Enrolled` / `Offers to Accepted` / `Offers to Enrolled` | Ever      | Funnel conversion-rate metrics between two funnel stages.                                                                       |

## Known data model caveats

These are permanent properties of how Finalsite works, not defects — they
explain real, recurring sources of count discrepancy between raw Finalsite
numbers and the dashboard:

- **Concurrent academic years, non-standardized rollover.** Two years of live
  student data can coexist; individual students/regions roll over on their own
  uncoordinated timeline.
- **Status dates are mutable and student-scoped, not year-scoped.** A status
  date is tied to the student record and can be overwritten when someone edits
  the status in the Finalsite UI — not an immutable audit trail.
- **`grouped_status_order` (the 8-stage funnel sequence) is a best-assumption
  ordering.** Real students can skip steps or move backward through
  Inquiries→...→Enrolled.
- **`detailed_status_ranking` (crosswalk sheet) is hand-duplicated into a
  hardcoded `status_order` CASE in `int_finalsite__status_report_unpivot.sql`,
  and the two can drift out of sync** (per this repo's convention against
  staging-layer joins to Google Sheets). Guarded by
  `test_int_finalsite__status_order_matches_crosswalk_ranking`.
- **Same-day status ties can pick the wrong "latest status," and this is
  permanent and unfixable at the data layer.** The pipeline only compares dates
  (not full timestamps), and the tie-break (`status_order desc`) assumes "higher
  rank wins" — which breaks for an exit status (e.g. `Parent Declined`, rank 15)
  vs. an in-progress one (`Enrollment In Progress`, rank 16) set the same day.
  **The established fix is the "Reset Protocol™":** (1) put the student in
  another status, (2) wait a day, (3) put them in the status you want — waiting
  a day breaks the date-tie so the new status wins outright. To fix: check the
  FRESH Dashboard's Progress-to-Goals tab for students on the dashboard but not
  in `Enrolled` status, using the **OPEN ROSTER** button (top right) to see
  every student's current status. To prevent: avoid giving a student two status
  changes on the same calendar day.
- **Ingestion lag.** `stg_finalsite__status_report` ingests via a
  sensor/file-drop-triggered Couchdrop SFTP asset, not a fixed cron — a status
  cleanup done late in one team member's workday (e.g. a Spain-based team member
  whose day ends mid-US-night) may not show on the dashboard until the next
  day's pull. Unconfirmed whether this specifically applies to Miami.
- **Fake/test Finalsite records not yet excluded inflate counts, at any time,
  not just at year rollover.** `stg_google_sheets__finalsite__exclude_ids` is
  enforced upstream of everything FRESH touches, but a test record created today
  isn't excluded until someone adds its id to the sheet.

## Annual rollover checklist

1. Review/update `stg_google_sheets__finalsite__exclude_ids` for the new cycle's
   Finalsite test/fake records.
2. Add the new cycle's `status_crosswalk` config row(s) — manual, no generator
   (the status→category mapping is institutional judgment, not computable).
3. Add the scaffold sheet's `-1` rows and any genuinely new grade/school rows —
   see the `fresh-dashboard` skill's `-1` candidate-row generator.
4. Add the goals sheet's gap rows for the new cycle — see the skill's
   goals-sheet gap-row generator.

## Open questions

- **Historical / multi-year scaffold reporting is not solved by this model.**
  `stg_powerschool__schools` is current-state only, and the scaffold sheet has
  never carried prior-year rows in practice. Needs a dedicated design discussion
  if this becomes a real requirement.
- **Whether the Miami/Focus carve-out can be removed** depends entirely on
  Focus's readiness as a data source — not yet determined as of this writing
  (2026-07-20).
````

- [ ] **Step 2: Add the mkdocs nav entry**

In `mkdocs.yml`, add alongside the other `reference/` entries (matching the
existing list format, e.g. near `Finalsite to Focus Import`):

```yaml
- FRESH Dashboard Data Model: reference/fresh-dashboard-data-model.md
```

- [ ] **Step 3: Trunk-check the doc**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/reference/fresh-dashboard-data-model.md mkdocs.yml </dev/null`
Fix any markdownlint issues found (fenced-block language tags, heading levels
incrementing by one, etc. — per `docs/CLAUDE.md` and root `CLAUDE.md`
conventions).

- [ ] **Step 4: Commit**

```bash
git add docs/reference/fresh-dashboard-data-model.md mkdocs.yml
git commit -m "docs: add FRESH dashboard reference doc"
```

---

## Task 12: Skill `.claude/skills/fresh-dashboard/`

**Files:**

- Create: `.claude/skills/fresh-dashboard/SKILL.md`

**Interfaces:**

- Consumes: `docs/reference/fresh-dashboard-data-model.md` (Task 11),
  `docs/superpowers/specs/2026-07-20-fresh-dashboard-scaffold-source-swap-design.md`.
- Produces: nothing — terminal task.

- [ ] **Step 1: Write the skill**

`.claude/skills/fresh-dashboard/SKILL.md` — mirror `gradebook-audit`'s
frontmatter and "Always read first" pattern:

````markdown
---
name: fresh-dashboard
description: >-
  Use when any question or task touches the FRESH dashboard's data model or its
  lineage. Triggers: explaining the scaffold/goals pipeline, debugging a count
  that doesn't match Finalsite, adding a new school/grade/year cycle,
  troubleshooting a student's status looking wrong, or working on
  int_finalsite__enrollment_scaffold, int_finalsite__goals_scaffold,
  rpt_tableau__fresh_dashboard_progress_to_goals, or
  rpt_tableau__fresh_dashboard_aggregated and their upstream models.
---

# FRESH Dashboard Data Model

## Always read first

- Reference doc:
  [`docs/reference/fresh-dashboard-data-model.md`](../../../docs/reference/fresh-dashboard-data-model.md)
- Design spec:
  [`docs/superpowers/specs/2026-07-20-fresh-dashboard-scaffold-source-swap-design.md`](../../../docs/superpowers/specs/2026-07-20-fresh-dashboard-scaffold-source-swap-design.md)
- Implementation plan:
  [`docs/superpowers/plans/2026-07-20-fresh-dashboard-scaffold-source-swap.md`](../../../docs/superpowers/plans/2026-07-20-fresh-dashboard-scaffold-source-swap.md)

**Key facts to confirm before touching anything:**

- `academic_year` is start-year form (AY2026-2027 = `2026`).
- Miami is **always** 100% sheet-sourced, regardless of
  `finalsite_scaffold_source` — a deliberate, temporary carve-out (Miami's SIS
  moved to Focus, not ready yet as a scaffold source). Don't "fix" this by
  trying to onboard Miami schools into `stg_powerschool__schools` — ask first.
- `grade_level = -1` means "whole-school total row" in this scaffold's
  convention — never conflate with PowerSchool's own use of negative grade
  levels (pre-registration/pre-K).

---

## For a non-engineer: "why does this number look wrong?"

Start here if you're on the school/enrollment team, not an engineer.

1. **Is the whole school/region off, or one specific student?**
   - Whole category (e.g. all Inquiries for a school) → likely a
     `status_crosswalk` mapping gap. Ask an engineer to check whether the
     detailed statuses Finalsite has for that school/year are all mapped in the
     crosswalk sheet (see "Troubleshooting a count discrepancy" below).
   - One specific student showing the wrong status → check the FRESH Dashboard's
     Progress-to-Goals tab, **OPEN ROSTER** button (top right), for that
     student's current status. If it looks wrong and you set two statuses on the
     same day in Finalsite, use the **Reset Protocol™**:
     1. Put them in another status.
     2. Wait a day.
     3. Put them in the status you want.
   - Numbers look inflated → check whether a test/fake Finalsite record needs
     adding to the exclusion sheet
     (`stg_google_sheets__finalsite__exclude_ids`).
   - A cleanup you did late in your day isn't showing → ingestion has a lag (see
     reference doc); it may show up the next day.

2. **Adding a new grade or school mid-cycle?** Ask an engineer to run the `-1`
   candidate-row generator and the goals gap-row generator (below) — don't
   hand-type full rows from scratch.

## For an engineer: troubleshooting a count discrepancy

Standard checks, roughly in order of likelihood:

1. **Missing crosswalk mapping**: pull
   `distinct detailed_status, enrollment_type` from
   `stg_finalsite__status_report` for the year in question, anti-join against
   `stg_google_sheets__finalsite__status_crosswalk`'s
   `(detailed_status, enrollment_type)` for that `_dagster_partition_key`.
   Anything present in Finalsite but absent from the crosswalk is silently
   dropped by `latest_status_calc`'s `inner join`.
2. **Invalid or QA-flagged rows**: for statuses that DO have a mapping, check
   `valid_detailed_status = false` or `qa_flag = true` — these are also silently
   excluded. `valid_detailed_status` specifically encodes "is this status
   legitimate for this enrollment_type (New vs. Returning)" — a `false` means a
   real data-entry mismatch upstream in Finalsite.
3. **Same-day status tie**: if one specific student's `latest_status` looks
   wrong (e.g. shows an in-progress status for a kid who actually
   withdrew/declined), check whether two statuses were set the same calendar day
   in Finalsite. This is a permanent, accepted Finalsite limitation, not a code
   bug — see the reference doc's "Known data model caveats" and use the Reset
   Protocol above, not a code fix.
4. **Fake/test student records**: check
   `stg_google_sheets__finalsite__exclude_ids` for the student in question — a
   test record not yet excluded inflates counts.
5. **Ingestion lag**: `stg_finalsite__status_report` is sensor/file-drop
   triggered (Couchdrop SFTP), not a fixed cron — a very recent Finalsite edit
   may not have landed yet.

## Rollover / maintenance generators

Both are ad hoc BigQuery MCP queries, run on demand — not persistent dbt models.
Both end with the same verify-and-confirm step: after the analyst pastes rows
into the sheet, rematerialize `int_finalsite__enrollment_scaffold` (or
`stg_google_sheets__finalsite__goals`'s consumers) and confirm the change
reached prod before telling them it's done.

### `-1` candidate-row generator (scaffold sheet)

Lists every currently-existing, non-Miami school missing its `grade_level = -1`
row in `stg_google_sheets__finalsite__school_scaffold` for the current academic
year — Miami needs its full spine, not just this generator's output (see the
Miami note above).

```sql
select distinct
  cy.academic_year,
  ps.region,
  ps.abbreviation as school,
  ps.school_number as schoolid,
  -1 as grade_level,
  'KTAF' as org,
from `teamster-332318`.kipptaf_powerschool.stg_powerschool__schools as ps
cross join (
  select academic_year
  from `teamster-332318`.kipptaf_finalsite.int_finalsite__current_academic_year
) as cy
left join `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__finalsite__school_scaffold as s
  on ps.school_number = s.schoolid
  and s.grade_level = -1
  and s.academic_year = cy.academic_year
where
  ps.state_excludefromreporting = 0
  -- extract_region logic inline since this is an ad hoc query, not a dbt model:
  and initcap(regexp_extract(ps._dbt_source_project, r'kipp(\w+)')) != 'Miami'
  and s.schoolid is null
```

### Goals-sheet gap-row generator

Three patterns — see the reference doc's "Goal definitions" section for which
`goal_type`/`goal_name` combos are `School` vs. `School/Grade Level` vs.
`Region/Grade Level`. For each, project the most recent existing year's
combo-set for that `schoolid` (or `region`, for `Region/Grade Level` rows)
forward onto the current scaffold, and list any
`(academic_year, region, schoolid, school, grade_level, goal_granularity, goal_type, goal_name)`
combo present in the scaffold/region set but absent from the current year's
goals sheet. A genuinely new school/grade has no prior-year pattern to project —
flag it for the analyst to pick goal types manually rather than silently
skipping it.

## Verified facts (don't re-derive these — reference them)

- `stg_powerschool__schools.school_level` is a single value **per school**
  (based on `high_grade`), not per grade — Sumner is base-classified `ES`
  network-wide there; this scaffold's own per-grade `CASE` (not that field) is
  what correctly produces `MS` for Sumner grades 5/6. Do not "fix" Sumner by
  reading `stg_powerschool__schools.school_level` directly.
- `schoolid` domains fully align between `stg_powerschool__schools` (filtered)
  and `int_people__location_crosswalk` for every case that matters — verified
  during design (see spec's "Verification" section).
````

- [ ] **Step 2: Trunk-check the skill file**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/fresh-dashboard/SKILL.md </dev/null`
Fix any issues.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/fresh-dashboard/SKILL.md
git commit -m "docs(skill): add fresh-dashboard maintenance skill"
```

---

## Task 13: Full-chain verification and cleanup

**Files:** none created/modified — verification only.

- [ ] **Step 1: Full chain build**

Run:
`uv run dbt build --select int_finalsite__enrollment_scaffold+ --target dev --defer --state <abs prod manifest path> --project-dir src/dbt/kipptaf`
Expected: every downstream model (goals_scaffold, both `rpt_` models, both new
tests) builds and passes.

- [ ] **Step 2: Compare against prod end-to-end**

Via BigQuery MCP, compare row counts and a sample of goal values in the
freshly-built dev `rpt_tableau__fresh_dashboard_progress_to_goals` and
`rpt_tableau__fresh_dashboard_aggregated` against the current prod tables.
Expect an exact match for AY2026 data (the refactor is behavior-preserving in
`blend` mode today; any difference means a bug, not an expected change).

- [ ] **Step 3: Confirm no stale refs remain**

```bash
grep -rn "int_google_sheets__finalsite__scaffold\|stg_google_sheets__finalsite__school_scaffold" src/dbt/kipptaf/models --include='*.sql' --include='*.yml' | grep -v target
```

Expected: the only remaining hits are inside
`int_finalsite__enrollment_scaffold.sql` itself (the sheet-side builder, which
still legitimately reads `stg_google_sheets__finalsite__school_scaffold`) and
its own properties yml.

- [ ] **Step 4: Trunk check everything touched**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__enrollment_scaffold.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__goals_scaffold.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__current_academic_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_progress_to_goals.sql \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__fresh_dashboard_aggregated.sql \
  src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__finalsite_student_scaffold.sql \
  </dev/null
```

Fix anything flagged.

- [ ] **Step 5: Final commit if any trunk fixes were needed**

```bash
git add -u
git commit -m "style: trunk fixes"
```

At this point the branch is ready for `superpowers:requesting-code-review` and a
PR against `main`, per this repo's PR conventions. </content>
