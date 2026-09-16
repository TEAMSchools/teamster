# Resolver score-anchors split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the resolver's six-way score union into a cron table model so
`int_assessments__resolved_section_enrollments` reads it once instead of
inlining it three times.

**Architecture:** New kipptaf intermediate table
`int_assessments__score_anchors` holds everything the resolver computed up to
`scores_mapped`, deduplicated by grain projection. The resolver drops those CTEs
and reads the table in `candidates_subject` and `scores_unresolved`. Output
columns and grain of the resolver do not change.

**Tech Stack:** dbt-bigquery via `uv run dbt`, dbt unit tests, BigQuery via
Application Default Credentials for the value-level proof.

Spec:
`docs/superpowers/specs/2026-09-14-resolver-score-anchors-split-design.md`.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors`.
  Every git call is `git -C <worktree>`; every file path starts with the
  worktree path. Shell variable for it below is lowercase `wt` (an uppercase
  name trips the Bash hook).
- Project dir: `<wt>/src/dbt/kipptaf`. Prod manifest for `--defer`:
  `/workspaces/teamster/src/dbt/kipptaf/target/prod` (absolute; the worktree has
  none).
- Never bare `dbt`, `python`. Always `uv run`.
- New model config, verbatim: `materialized: table`,
  `automation_condition.cron_schedule: 0 0,10,13,15,17 * * *`.
- New model columns, in order: `powerschool_student_number`,
  `canonical_assessment_id`, `academic_year`, `administration_period`,
  `subject_area`, `_dbt_source_project`, `anchor_date`, `source_type`,
  `score_grain_key`. No `course_subject`.
- `score_grain_key` inputs, in order: `powerschool_student_number`,
  `_dbt_source_project`, `source_type`, `canonical_assessment_id`,
  `academic_year`, `administration_period`, `subject_area`.
- Resolver output columns, types, and grain are unchanged.
- No `QUALIFY`, no `select * except`, no `group by all`, no `order by` outside a
  window (`.claude/rules/dbt-sql.md`).
- Unit-test fixture scalars unquoted; `format: sql` for any input mocking
  `int_assessments__score_anchors` (the relation does not exist in the deferred
  environment, so dict fixtures fail introspection).
- Before every push: run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- Commit messages via
  `git commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt`, ending
  with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Feature-branch push and PR creation run on the session's own credentials. Do
  not hand them to the user.

---

### Task 0: Worktree ready

**Files:** none edited.

- [ ] **Step 1: Install dbt packages in the worktree**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
uv run dbt deps --project-dir $wt/src/dbt/kipptaf
```

Expected: ends with packages installed, no error.

- [ ] **Step 2: Confirm the prod manifest is fresh**

```bash
ls -la /workspaces/teamster/src/dbt/kipptaf/target/prod/manifest.json
```

Expected: mtime within the last few days. If older than the 2026-09-14 merge of
#5308, regenerate:

```bash
uv run dbt parse --target prod --project-dir /workspaces/teamster/src/dbt/kipptaf --target-path target/prod
```

---

### Task 1: New model `int_assessments__score_anchors`

**Files:**

- Create:
  `<wt>/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql`
- Create:
  `<wt>/src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__score_anchors.yml`

**Interfaces:**

- Consumes: `int_assessments__scaffold`,
  `int_assessments__assessments_canonical`, `int_pearson__all_assessments`,
  `int_fldoe__all_assessments`, `int_iready__diagnostic_results`,
  `stg_renlearn__star`, `int_amplify__all_assessments` (all existing,
  unchanged).
- Produces: table `int_assessments__score_anchors` with the nine columns in the
  Global Constraints order. `score_grain_key` is a
  `dbt_utils.generate_surrogate_key` string. Unique on the seven grain columns
  plus `anchor_date`.

- [ ] **Step 1: Write the properties yml with two unit tests (they fail until
      the model exists)**

Write
`<wt>/src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__score_anchors.yml`:

```yaml
models:
  - name: int_assessments__score_anchors
    description: >-
      Every assessment score the section resolver tries to place, with the one
      date it anchors on. One row per score grain (student, region, source type,
      canonical assessment, academic year, administration period, subject area)
      and anchor date. Six source branches feed it — internal Illuminate scores
      anchored on the canonical administered date, NJ state (Pearson) and FL
      state (FLDOE) scores on their test date, and iReady, STAR, and DIBELS
      benchmark composites on their completion, screening, or client date.
      Internal scores collapse to one row per student, canonical assessment, and
      region on the earliest administered date. Rows with no anchor date or no
      student are out of scope and dropped. Byte-identical duplicate rows from a
      source (re-pulled iReady and STAR sittings) collapse; a score with two
      different anchor dates keeps both rows, since each date is a separate
      chance at an enrollment window. Read by
      int_assessments__resolved_section_enrollments, which references it three
      times; materializing it once here is what keeps that model's BigQuery plan
      shallow.
    config:
      materialized: table
      meta:
        dagster:
          # Same tick as int_assessments__scaffold,
          # int_assessments__course_enrollments, and the resolver so
          # ~any_deps_in_progress orders it before the resolver in one pass.
          # Refs #5261
          automation_condition:
            cron_schedule: 0 0,10,13,15,17 * * *
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - powerschool_student_number
              - _dbt_source_project
              - source_type
              - canonical_assessment_id
              - academic_year
              - administration_period
              - subject_area
              - anchor_date
    columns:
      - name: source_type
        data_type: string
        description: >-
          Source branch that produced the score row. One of internal
          (Illuminate-sourced), state_nj (Pearson NJ), state_fl (FLDOE FL),
          iready (i-Ready diagnostics), star (Renaissance STAR), or dibels
          (Amplify DIBELS benchmark composites).
        data_tests:
          - not_null
          - accepted_values:
              arguments:
                values: [internal, state_nj, state_fl, iready, star, dibels]
      - name: powerschool_student_number
        data_type: int64
        description: >-
          Student identifier. Sourced from int_assessments__scaffold for
          internal scores and from each vendor or state intermediate otherwise.
        config:
          meta:
            source_column: int_assessments__scaffold.powerschool_student_number
      - name: canonical_assessment_id
        data_type: int64
        description: >-
          Canonical assessment identifier grouping member assessments into one
          logical assessment. Populated only for internal scores; NULL for state
          and vendor rows.
        config:
          meta:
            source_column: int_assessments__scaffold.canonical_assessment_id
      - name: academic_year
        data_type: int64
        description: >-
          Academic year of the sitting. Populated for state and vendor rows;
          NULL for internal rows, whose year comes from the enrollment window
          the resolver matches.
        config:
          meta:
            source_column: int_pearson__all_assessments.academic_year
      - name: administration_period
        data_type: string
        description: >-
          Administration window label within the academic year. Populated for
          state, iReady, STAR, and DIBELS rows; NULL for internal rows. For
          iReady rows this is the reporting-terms window (BOY / MOY / EOY /
          Outside Round) from `test_round`.
        config:
          meta:
            source_column: int_pearson__all_assessments.administration_period
      - name: subject_area
        data_type: string
        description: >-
          Subject area aligned to illuminate_subject_area values in
          int_assessments__course_enrollments. For internal scores this is the
          scaffold subject_area; for state and vendor scores it is the
          `illuminate_subject` column mapped upstream (e.g. Reading -> Text
          Study, Math -> Mathematics).
        config:
          meta:
            source_column: int_assessments__scaffold.subject_area
      - name: _dbt_source_project
        data_type: string
        description: >-
          Region identifier (kippnewark, kippcamden, kippmiami, kipppaterson) of
          the score.
        config:
          meta:
            source_column: int_assessments__scaffold._dbt_source_project
      - name: anchor_date
        data_type: date
        description: >-
          The date the resolver matches against enrollment windows. The
          canonical administered date for internal scores, the test date for
          state scores, and the completion, screening, or client date for vendor
          scores. Not the corrupt Illuminate date_taken.
        config:
          meta:
            source_column: int_assessments__assessments_canonical.administered_date
      - name: score_grain_key
        data_type: string
        description: >-
          Surrogate key over the seven grain columns (student, region, source
          type, canonical assessment, academic year, administration period,
          subject area). The resolver ranks section candidates within this key
          and anti-joins tier 2 on it. Not unique on its own — a score with two
          anchor dates shares one key across two rows — so the uniqueness test
          is on the grain columns plus anchor_date, and this column carries no
          `unique` test by design.

unit_tests:
  - name: test_internal_collapses_to_one_row_per_canonical
    description: >-
      Two scaffold rows for the same student, canonical assessment, and region
      collapse to one internal row anchored on the canonical administered date.
      A replacement row and a non-internal row are excluded.
    model: int_assessments__score_anchors
    given:
      - input: ref('int_assessments__scaffold')
        rows:
          - {
              powerschool_student_number: 1,
              canonical_assessment_id: 100,
              _dbt_source_project: kippnewark,
              subject_area: Mathematics,
              is_internal_assessment: true,
              is_replacement: false,
            }
          - {
              powerschool_student_number: 1,
              canonical_assessment_id: 100,
              _dbt_source_project: kippnewark,
              subject_area: Mathematics,
              is_internal_assessment: true,
              is_replacement: false,
            }
          - {
              powerschool_student_number: 1,
              canonical_assessment_id: 100,
              _dbt_source_project: kippnewark,
              subject_area: Mathematics,
              is_internal_assessment: true,
              is_replacement: true,
            }
          - {
              powerschool_student_number: 1,
              canonical_assessment_id: 100,
              _dbt_source_project: kippnewark,
              subject_area: Mathematics,
              is_internal_assessment: false,
              is_replacement: false,
            }
      - input: ref('int_assessments__assessments_canonical')
        rows:
          - { canonical_assessment_id: 100, administered_date: 2024-03-04 }
      - input: ref('int_pearson__all_assessments')
        rows: []
      - input: ref('int_fldoe__all_assessments')
        rows: []
      - input: ref('int_iready__diagnostic_results')
        rows: []
      - input: ref('stg_renlearn__star')
        rows: []
      - input: ref('int_amplify__all_assessments')
        rows: []
    expect:
      rows:
        - {
            powerschool_student_number: 1,
            canonical_assessment_id: 100,
            _dbt_source_project: kippnewark,
            subject_area: Mathematics,
            anchor_date: 2024-03-04,
            source_type: internal,
          }

  - name: test_duplicate_vendor_rows_collapse
    description: >-
      Two byte-identical iReady rows (a re-pulled sitting) produce one output
      row. A third row for the same score on a different completion date is a
      separate anchor and is kept.
    model: int_assessments__score_anchors
    given:
      - input: ref('int_assessments__scaffold')
        rows: []
      - input: ref('int_assessments__assessments_canonical')
        rows: []
      - input: ref('int_pearson__all_assessments')
        rows: []
      - input: ref('int_fldoe__all_assessments')
        rows: []
      - input: ref('int_iready__diagnostic_results')
        format: sql
        rows: |
          select
              5 as student_id,
              2024 as academic_year_int,
              'BOY' as test_round,
              'Text Study' as illuminate_subject,
              'kippnewark' as _dbt_source_project,
              date('2024-09-15') as completion_date,
              650 as overall_scale_score
          union all
          select
              5 as student_id,
              2024 as academic_year_int,
              'BOY' as test_round,
              'Text Study' as illuminate_subject,
              'kippnewark' as _dbt_source_project,
              date('2024-09-15') as completion_date,
              650 as overall_scale_score
          union all
          select
              5 as student_id,
              2024 as academic_year_int,
              'BOY' as test_round,
              'Text Study' as illuminate_subject,
              'kippnewark' as _dbt_source_project,
              date('2024-09-22') as completion_date,
              655 as overall_scale_score
      - input: ref('stg_renlearn__star')
        rows: []
      - input: ref('int_amplify__all_assessments')
        rows: []
    expect:
      rows:
        - {
            powerschool_student_number: 5,
            academic_year: 2024,
            administration_period: BOY,
            subject_area: Text Study,
            anchor_date: 2024-09-15,
            source_type: iready,
          }
        - {
            powerschool_student_number: 5,
            academic_year: 2024,
            administration_period: BOY,
            subject_area: Text Study,
            anchor_date: 2024-09-22,
            source_type: iready,
          }
```

- [ ] **Step 2: Run parse to see the yml fail on the missing model**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
uv run dbt parse --project-dir $wt/src/dbt/kipptaf --target dev 2>&1 | tail -5
```

Expected: a parse error naming `int_assessments__score_anchors` as an unknown
model.

- [ ] **Step 3: Write the model SQL**

Write
`<wt>/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql`:

```sql
with
    -- internal scores anchor on the scheduled administration date. date_taken
    -- is occasionally corrupt (epoch / year-2000 sentinels) and anchoring on it
    -- dropped scores whose bad date missed every enrollment window (#4183).
    internal_anchored as (
        select
            sc.powerschool_student_number,
            sc.canonical_assessment_id,
            sc.subject_area,
            sc._dbt_source_project,

            c.administered_date as anchor_date,

            row_number() over (
                partition by
                    sc.powerschool_student_number,
                    sc.canonical_assessment_id,
                    sc._dbt_source_project
                order by c.administered_date asc
            ) as rn,
        from {{ ref("int_assessments__scaffold") }} as sc
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on sc.canonical_assessment_id = c.canonical_assessment_id
        where sc.is_internal_assessment and not sc.is_replacement
    ),

    internal_scores as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            subject_area,
            _dbt_source_project,
            anchor_date,

            cast(null as int64) as academic_year,
            cast(null as string) as administration_period,

            'internal' as source_type,
        from internal_anchored
        where rn = 1
    ),

    -- rows with no test date or no student cannot resolve -> dropped
    state_nj_scores as (
        select
            localstudentidentifier as powerschool_student_number,
            academic_year,
            administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            test_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'state_nj' as source_type,
        from {{ ref("int_pearson__all_assessments") }}
        where test_date is not null and localstudentidentifier is not null
    ),

    state_fl_scores as (
        select
            student_number as powerschool_student_number,
            academic_year,
            administration_window as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            test_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'state_fl' as source_type,
        from {{ ref("int_fldoe__all_assessments") }}
        where test_date is not null and student_number is not null
    ),

    iready_scores as (
        select
            student_id as powerschool_student_number,
            academic_year_int as academic_year,
            test_round as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            completion_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'iready' as source_type,
        from {{ ref("int_iready__diagnostic_results") }}
        where completion_date is not null and overall_scale_score is not null
    ),

    -- rows without a crosswalk-resolved project cannot join course
    -- enrollments and are dropped
    star_scores as (
        select
            student_display_id as powerschool_student_number,
            academic_year,
            screening_period_window_name as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            completed_date_value as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'star' as source_type,
        from {{ ref("stg_renlearn__star") }}
        where
            completed_date_value is not null
            and unified_score is not null
            and _dbt_source_project is not null
    ),

    -- benchmark composites only; PM probes and subskill measures are out of
    -- scope
    dibels_scores as (
        select
            student_number as powerschool_student_number,
            academic_year,
            `period` as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            client_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'dibels' as source_type,
        from {{ ref("int_amplify__all_assessments") }}
        where
            assessment_type = 'Benchmark'
            and measure_standard = 'Composite'
            and client_date is not null
    ),

    scores as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from internal_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from state_nj_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from state_fl_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from iready_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from star_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from dibels_scores
    ),

    scores_keyed as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "powerschool_student_number",
                        "_dbt_source_project",
                        "source_type",
                        "canonical_assessment_id",
                        "academic_year",
                        "administration_period",
                        "subject_area",
                    ]
                )
            }} as score_grain_key,
        from scores
    )

-- grain projection, not dup-masking: every projected column is in the grain
-- (score_grain_key inputs + anchor_date), so only byte-identical rows coalesce
select distinct
    powerschool_student_number,
    canonical_assessment_id,
    academic_year,
    administration_period,
    subject_area,
    _dbt_source_project,
    anchor_date,
    source_type,
    score_grain_key,
from scores_keyed
```

- [ ] **Step 4: Parse, then run the two unit tests**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
uv run dbt parse --project-dir $wt/src/dbt/kipptaf --target dev 2>&1 | tail -3
uv run dbt test --select "int_assessments__score_anchors,test_type:unit" \
  --project-dir $wt/src/dbt/kipptaf --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -15
```

Expected: `PASS=2 WARN=0 ERROR=0`. If
`test_internal_collapses_to_one_row_per_canonical` returns two rows, the
`where rn = 1` filter is missing or in the wrong CTE.

- [ ] **Step 5: Build the model into the dev schema and run its data tests**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
uv run dbt build --select int_assessments__score_anchors \
  --project-dir $wt/src/dbt/kipptaf --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -15
```

Expected: model
`OK created sql table model zz_cbini_kipptaf_assessments.int_assessments__score_anchors`,
the `unique_combination_of_columns` test PASS, `not_null` and `accepted_values`
PASS, both unit tests PASS.

- [ ] **Step 6: Sanity-check the row count against the spec's measurement**

Through the BigQuery MCP (`mcp__bigquery__execute_sql`):

```sql
select source_type, count(*) as n
from `teamster-332318`.zz_cbini_kipptaf_assessments.int_assessments__score_anchors
group by source_type
```

Expected, within a day's drift of the spec table: internal 2,262,873; state_nj
71,996; state_fl 20,285; iready 264,787; star 7,965; dibels 62,485. iready and
star must equal the "distinct grain + anchor_date" column, not the raw row
count.

- [ ] **Step 7: Lint and commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__score_anchors.yml </dev/null
```

Fix anything reported (a `trunk fmt` on the same paths handles formatting).
Then:

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
git -C $wt add src/dbt/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__score_anchors.yml
printf 'perf(assessments): add int_assessments__score_anchors table\n\nMaterializes the six-way score union the section resolver inlined three\ntimes per build, on the same cron tick as the resolver.\n\nRefs #5261\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n' \
  > /workspaces/teamster/.claude/scratch/commit-msg.txt
git -C $wt commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

---

### Task 2: Resolver reads the new table

**Files:**

- Modify:
  `<wt>/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`
  (replace lines 1-257; edit the two `from scores_mapped` sites and the tier-1
  join predicate)
- Modify:
  `<wt>/src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__resolved_section_enrollments.yml`
  (model description; `unit_tests:` block, lines 150-423)

**Interfaces:**

- Consumes: `int_assessments__score_anchors` (Task 1) columns
  `powerschool_student_number`, `canonical_assessment_id`, `academic_year`,
  `administration_period`, `subject_area`, `_dbt_source_project`, `anchor_date`,
  `source_type`, `score_grain_key`.
- Produces: unchanged resolver output.

- [ ] **Step 1: Rewrite the five unit tests first (they fail until the SQL
      changes)**

Replace everything from `unit_tests:` (line 150) to the end of the file with:

```yaml
unit_tests:
  - name: test_subject_section_in_window_wins
    description: >-
      Subject section whose enrollment window contains the anchor date resolves
      at tier 1 (resolution_type=subject_section). The second section for the
      same student starts after the anchor date and is filtered out by the
      half-open window join.
    model: int_assessments__resolved_section_enrollments
    given:
      - input: ref('int_assessments__score_anchors')
        format: sql
        rows: |
          select
              1 as powerschool_student_number,
              100 as canonical_assessment_id,
              cast(null as int64) as academic_year,
              cast(null as string) as administration_period,
              'Mathematics' as subject_area,
              'kippnewark' as _dbt_source_project,
              date('2024-03-04') as anchor_date,
              'internal' as source_type,
              'k1' as score_grain_key
      - input: ref('int_assessments__course_enrollments')
        rows:
          - {
              powerschool_student_number: 1,
              _dbt_source_project: kippnewark,
              illuminate_subject_area: Mathematics,
              courses_credittype: MATH,
              cc_dateenrolled: 2024-01-01,
              cc_dateleft: 2025-06-15,
              cc_dcid: 111,
              powerschool_school_id: 73252,
              region: Newark,
            }
          - {
              powerschool_student_number: 1,
              _dbt_source_project: kippnewark,
              illuminate_subject_area: Mathematics,
              courses_credittype: MATH,
              cc_dateenrolled: 2025-09-01,
              cc_dateleft: 2026-06-15,
              cc_dcid: 222,
              powerschool_school_id: 73252,
              region: Newark,
            }
    expect:
      rows:
        - {
            powerschool_student_number: 1,
            canonical_assessment_id: 100,
            resolution_type: subject_section,
            cc_source_project: kippnewark,
          }

  - name: test_homeroom_fallback_when_no_subject_section
    description: >-
      When no subject section's enrollment window contains the anchor date the
      homeroom section active on that date is used and resolution_type is
      homeroom.
    model: int_assessments__resolved_section_enrollments
    given:
      - input: ref('int_assessments__score_anchors')
        format: sql
        rows: |
          select
              2 as powerschool_student_number,
              200 as canonical_assessment_id,
              cast(null as int64) as academic_year,
              cast(null as string) as administration_period,
              'ELA' as subject_area,
              'kippcamden' as _dbt_source_project,
              date('2024-11-01') as anchor_date,
              'internal' as source_type,
              'k2' as score_grain_key
      - input: ref('int_assessments__course_enrollments')
        rows:
          - {
              powerschool_student_number: 2,
              _dbt_source_project: kippcamden,
              illuminate_subject_area: HR,
              courses_credittype: HR,
              cc_dateenrolled: 2024-09-01,
              cc_dateleft: 2025-06-15,
              cc_dcid: 333,
              powerschool_school_id: 179902,
              region: Camden,
            }
    expect:
      rows:
        - {
            powerschool_student_number: 2,
            canonical_assessment_id: 200,
            resolution_type: homeroom,
          }

  - name: test_no_matching_section_drops_row
    description: >-
      A score with no matching subject section and no matching homeroom section
      produces no output row.
    model: int_assessments__resolved_section_enrollments
    given:
      - input: ref('int_assessments__score_anchors')
        format: sql
        rows: |
          select
              3 as powerschool_student_number,
              300 as canonical_assessment_id,
              cast(null as int64) as academic_year,
              cast(null as string) as administration_period,
              'Science' as subject_area,
              'kippmiami' as _dbt_source_project,
              date('2024-10-01') as anchor_date,
              'internal' as source_type,
              'k3' as score_grain_key
      - input: ref('int_assessments__course_enrollments')
        rows: []
    expect:
      rows: []

  - name: test_state_nj_resolves_subject_section
    description: >-
      A NJ state score resolves to a subject section active on its test_date and
      source_type is state_nj.
    model: int_assessments__resolved_section_enrollments
    given:
      - input: ref('int_assessments__score_anchors')
        format: sql
        rows: |
          select
              4 as powerschool_student_number,
              cast(null as int64) as canonical_assessment_id,
              2024 as academic_year,
              'Spring' as administration_period,
              'Mathematics' as subject_area,
              'kippnewark' as _dbt_source_project,
              date('2025-04-10') as anchor_date,
              'state_nj' as source_type,
              'k4' as score_grain_key
      - input: ref('int_assessments__course_enrollments')
        rows:
          - {
              powerschool_student_number: 4,
              _dbt_source_project: kippnewark,
              illuminate_subject_area: Mathematics,
              courses_credittype: MATH,
              cc_dateenrolled: 2024-09-01,
              cc_dateleft: 2025-06-15,
              cc_dcid: 444,
              powerschool_school_id: 73252,
              region: Newark,
            }
    expect:
      rows:
        - {
            powerschool_student_number: 4,
            academic_year: 2024,
            administration_period: Spring,
            subject_area: Mathematics,
            source_type: state_nj,
            resolution_type: subject_section,
          }

  - name: test_iready_dibels_source_type_prevents_grain_collision
    description: >-
      Regression test for #3625 (fixed in a743b7d6c). An iReady Reading score
      and a DIBELS Composite score for the same student/project/academic
      year/administration_period/subject_area (Text Study) carry distinct
      score_grain_key values because source_type is a key input. Both must
      resolve to the subject section and survive as distinct output rows -- the
      resolved-tier dedupe partitions on score_grain_key, so a shared key would
      silently collapse them into one.
    model: int_assessments__resolved_section_enrollments
    given:
      - input: ref('int_assessments__score_anchors')
        format: sql
        rows: |
          select
              5 as powerschool_student_number,
              cast(null as int64) as canonical_assessment_id,
              2024 as academic_year,
              'BOY' as administration_period,
              'Text Study' as subject_area,
              'kippnewark' as _dbt_source_project,
              date('2024-09-15') as anchor_date,
              'iready' as source_type,
              'k5-iready' as score_grain_key
          union all
          select
              5 as powerschool_student_number,
              cast(null as int64) as canonical_assessment_id,
              2024 as academic_year,
              'BOY' as administration_period,
              'Text Study' as subject_area,
              'kippnewark' as _dbt_source_project,
              date('2024-09-20') as anchor_date,
              'dibels' as source_type,
              'k5-dibels' as score_grain_key
      - input: ref('int_assessments__course_enrollments')
        rows:
          - {
              powerschool_student_number: 5,
              _dbt_source_project: kippnewark,
              illuminate_subject_area: Text Study,
              courses_credittype: ELA,
              cc_dateenrolled: 2024-09-01,
              cc_dateleft: 2025-06-15,
              cc_dcid: 555,
              powerschool_school_id: 73252,
              region: Newark,
            }
    expect:
      rows:
        - {
            powerschool_student_number: 5,
            source_type: iready,
            student_section_enrollment_key: 862d5edd93004a2ab12782487a3292a7,
          }
        - {
            powerschool_student_number: 5,
            source_type: dibels,
            student_section_enrollment_key: 862d5edd93004a2ab12782487a3292a7,
          }
```

- [ ] **Step 2: Run the resolver unit tests to see them fail on the old SQL**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
uv run dbt test --select "int_assessments__resolved_section_enrollments,test_type:unit" \
  --project-dir $wt/src/dbt/kipptaf --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -15
```

Expected: a parse or compile error saying the model does not depend on
`int_assessments__score_anchors` (the fixture mocks a ref the SQL does not
have).

- [ ] **Step 3: Rewrite the resolver SQL**

Replace the whole file
`<wt>/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`
with:

```sql
with
    candidates_subject as (
        select
            s.powerschool_student_number,
            s.canonical_assessment_id,
            s.academic_year,
            s.administration_period,
            s.subject_area,
            s._dbt_source_project,
            s.source_type,
            s.score_grain_key,
            s.anchor_date,

            ce.cc_dcid,
            ce._dbt_source_project as cc_source_project,
            ce.cc_dateleft,
            ce.powerschool_school_id,
            ce.region,

            1 as tier,

            'subject_section' as resolution_type,
        from {{ ref("int_assessments__score_anchors") }} as s
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on s.powerschool_student_number = ce.powerschool_student_number
            and s._dbt_source_project = ce._dbt_source_project
            and s.subject_area = ce.illuminate_subject_area
            and s.anchor_date >= ce.cc_dateenrolled
            and s.anchor_date < ce.cc_dateleft
            -- only sections with a real course-enrollment row resolve to a
            -- dim_student_section_enrollments FK; synthetic ES-Writing (RHET)
            -- inventory rows carry cc_dcid = null and have no dim row
            and ce.cc_dcid is not null
    ),

    -- grain projection, not dup-masking
    resolved_subject_keys as (select distinct score_grain_key, from candidates_subject),

    scores_unresolved as (
        select s.*,
        from {{ ref("int_assessments__score_anchors") }} as s
        left join resolved_subject_keys as cs on s.score_grain_key = cs.score_grain_key
        where cs.score_grain_key is null
    ),

    candidates_homeroom as (
        select
            s.powerschool_student_number,
            s.canonical_assessment_id,
            s.academic_year,
            s.administration_period,
            s.subject_area,
            s._dbt_source_project,
            s.source_type,
            s.score_grain_key,
            s.anchor_date,

            ce.cc_dcid,
            ce._dbt_source_project as cc_source_project,
            ce.cc_dateleft,
            ce.powerschool_school_id,
            ce.region,

            2 as tier,

            'homeroom' as resolution_type,
        from scores_unresolved as s
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on s.powerschool_student_number = ce.powerschool_student_number
            and s._dbt_source_project = ce._dbt_source_project
            and ce.courses_credittype = 'HR'
            and s.anchor_date >= ce.cc_dateenrolled
            and s.anchor_date < ce.cc_dateleft
            and ce.cc_dcid is not null
    ),

    all_candidates as (
        select *,
        from candidates_subject

        union all

        select *,
        from candidates_homeroom
    ),

    -- one section per score: prefer the subject section (tier 1) over homeroom,
    -- then the section that ends latest among ties within a tier
    all_candidates_ranked as (
        select
            *,

            row_number() over (
                partition by score_grain_key
                order by tier asc, cc_dateleft desc, cc_dcid desc
            ) as rn,
        from all_candidates
    ),

    resolved as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            source_type,
            resolution_type,

            cc_dcid,
            cc_source_project,
            powerschool_school_id,
            region,
        from all_candidates_ranked
        where rn = 1
    )

select
    powerschool_student_number,
    canonical_assessment_id,
    academic_year,
    administration_period,
    subject_area,
    _dbt_source_project,
    cc_source_project,
    source_type,
    resolution_type,

    -- the resolved section's school and region. Carried so consumers can resolve
    -- a score's reporting quarter from the score's OWN date (#4484); this model
    -- is one row per score GRAIN, so its anchor_date cannot stand in for the
    -- date of every score row sharing that grain.
    powerschool_school_id,
    region,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "cc_source_project"]) }}
    as student_section_enrollment_key,
from resolved
```

The only logic edits against the current file: the two `from scores_mapped`
sites now read the ref, and `s.course_subject = ce.illuminate_subject_area`
became `s.subject_area = ce.illuminate_subject_area`. Everything from
`resolved_subject_keys` down is byte-identical to the current file.

- [ ] **Step 4: Update the model description**

In the resolver properties yml, append this sentence to the end of the top-level
`description:` block (after "...reporting quarter by date."):

```text
      The score rows themselves come from int_assessments__score_anchors, which
      carries each score's anchor date and score_grain_key.
```

- [ ] **Step 5: Run the resolver unit tests**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
uv run dbt test --select "int_assessments__resolved_section_enrollments,test_type:unit" \
  --project-dir $wt/src/dbt/kipptaf --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -15
```

Expected: `PASS=5 WARN=0 ERROR=0`.

- [ ] **Step 6: Build the new chain into dev, with both models selected**

Both models must be in `--select`: `--favor-state` resolves an unselected
`int_assessments__score_anchors` to prod, where it does not exist.

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
uv run dbt build --select int_assessments__score_anchors int_assessments__resolved_section_enrollments \
  --project-dir $wt/src/dbt/kipptaf --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -25
```

Expected: both tables created, all unit tests PASS, all data tests PASS,
including the singular test
`int_assessments__resolved_section_enrollments__unique_per_score`.

- [ ] **Step 7: Lint and commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql \
  src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__resolved_section_enrollments.yml </dev/null
```

Then:

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
git -C $wt add -u
printf 'perf(assessments): read score anchors from a table in the section resolver\n\nThe six-way score union was inlined three times per build (154 stages,\n424 parallel inputs broadcasting the 706k-row course inventory). Reading\nint_assessments__score_anchors once removes the inlining. Output columns\nand grain are unchanged.\n\nRefs #5261\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n' \
  > /workspaces/teamster/.claude/scratch/commit-msg.txt
git -C $wt commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

---

### Task 3: Value-level proof against prod

**Files:**

- Create (scratch, not committed):
  `/workspaces/teamster/.claude/scratch/resolver_proof.py`

**Interfaces:**

- Consumes: the compiled SQL of the old resolver (from the main checkout, at
  `origin/main`) and of the new model plus new resolver (from the worktree).
- Produces: three counts recorded in the PR body.

- [ ] **Step 1: Compile old and new SQL against prod schemas**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
uv run dbt compile --select int_assessments__resolved_section_enrollments \
  --project-dir /workspaces/teamster/src/dbt/kipptaf --target prod \
  --target-path target/proof 2>&1 | tail -3
uv run dbt compile --select int_assessments__score_anchors int_assessments__resolved_section_enrollments \
  --project-dir $wt/src/dbt/kipptaf --target prod --target-path target/proof 2>&1 | tail -3
```

Expected: three compiled files exist:

- `/workspaces/teamster/src/dbt/kipptaf/target/proof/compiled/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`
  (old)
- `<wt>/src/dbt/kipptaf/target/proof/compiled/kipptaf/models/assessments/intermediate/int_assessments__score_anchors.sql`
  (new model)
- `<wt>/src/dbt/kipptaf/target/proof/compiled/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`
  (new resolver; references
  `` `teamster-332318`.`kipptaf_assessments`.`int_assessments__score_anchors` ``,
  which does not exist in prod yet)

`dbt compile --target prod` writes nothing to the warehouse.

- [ ] **Step 2: Write the proof script**

Write `/workspaces/teamster/.claude/scratch/resolver_proof.py`:

```python
"""Old resolver vs new chain, same prod snapshot, one query. Expect 0/0/0."""

from pathlib import Path

from google.cloud import bigquery

main = Path("/workspaces/teamster/src/dbt/kipptaf/target/proof/compiled/kipptaf")
wt = Path(
    "/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors"
    "/src/dbt/kipptaf/target/proof/compiled/kipptaf"
)
rel = "models/assessments/intermediate"

old_sql = (main / rel / "int_assessments__resolved_section_enrollments.sql").read_text()
anchors_sql = (wt / rel / "int_assessments__score_anchors.sql").read_text()
new_sql = (wt / rel / "int_assessments__resolved_section_enrollments.sql").read_text()

anchors_ref = "`teamster-332318`.`kipptaf_assessments`.`int_assessments__score_anchors`"
assert new_sql.count(anchors_ref) == 2, new_sql.count(anchors_ref)
new_sql = new_sql.replace(anchors_ref, "anchors")

cols = [
    "powerschool_student_number",
    "canonical_assessment_id",
    "academic_year",
    "administration_period",
    "subject_area",
    "_dbt_source_project",
    "cc_source_project",
    "source_type",
    "resolution_type",
    "powerschool_school_id",
    "region",
    "student_section_enrollment_key",
]
grain = [
    "powerschool_student_number",
    "_dbt_source_project",
    "source_type",
    "canonical_assessment_id",
    "academic_year",
    "administration_period",
    "subject_area",
]
fmt = "format('" + "|".join(["%T"] * len(grain)) + "', " + ", ".join(grain) + ")"
payload = "to_json_string(struct(" + ", ".join(cols) + "))"

sql = f"""
with
    anchors as ({anchors_sql}),
    old as (select {fmt} as k, {payload} as v from ({old_sql})),
    new as (select {fmt} as k, {payload} as v from ({new_sql}))
select
    countif(new.k is null) as only_in_old,
    countif(old.k is null) as only_in_new,
    countif(old.k is not null and new.k is not null and old.v != new.v) as differing,
    count(*) as total_keys,
from old
full outer join new on old.k = new.k
"""

client = bigquery.Client(project="teamster-332318")
row = list(client.query(sql).result())[0]
print(dict(row))
assert row["only_in_old"] == 0 and row["only_in_new"] == 0 and row["differing"] == 0, dict(row)
print("PROOF OK")
```

- [ ] **Step 3: Run it**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
VIRTUAL_ENV= uv --directory $wt run python /workspaces/teamster/.claude/scratch/resolver_proof.py
```

Expected: a dict with `only_in_old: 0`, `only_in_new: 0`, `differing: 0`,
`total_keys` near 2,655,272, then `PROOF OK`. A nonzero `differing` means the
`distinct` changed a tie-break; inspect a sample before touching the SQL, do not
widen the dedup.

If the query fails with a nested-view or complexity error, the two compiled
bodies expanded too many views in one statement. Fall back to building the old
resolver into a second dev table from the main checkout
(`uv run dbt build --select int_assessments__resolved_section_enrollments --project-dir /workspaces/teamster/src/dbt/kipptaf --target dev --defer --favor-state --state target/prod`)
and comparing the two dev tables with the same full outer join; note in the PR
that the two builds were minutes apart.

- [ ] **Step 4: Record the counts**

Copy the printed dict into `/workspaces/teamster/.claude/scratch/proof.txt` for
the PR body in Task 4. Delete `resolver_proof.py` and the two `target/proof`
directories afterwards:

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
rm -rf /workspaces/teamster/src/dbt/kipptaf/target/proof $wt/src/dbt/kipptaf/target/proof
rm /workspaces/teamster/.claude/scratch/resolver_proof.py
```

---

### Task 4: Push and open the PR

**Files:**

- Read: `<wt>/.github/pull_request_template.md`

- [ ] **Step 1: Final lint over everything the branch touched**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C $wt diff --name-only origin/main...HEAD) </dev/null
```

Expected: `No issues`. Fix and amend into a new commit otherwise.

- [ ] **Step 2: Push**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-resolver-score-anchors
git -C $wt push -u origin cbini/perf/claude-resolver-score-anchors
```

- [ ] **Step 3: Open the PR**

Read `<wt>/.github/pull_request_template.md` and fill every section in place.
Title:
`perf(assessments): split the resolver score union into int_assessments__score_anchors`.
Body must include `Refs #5261`, the proof counts from
`/workspaces/teamster/.claude/scratch/proof.txt`, the before number (15.15 slot
hours / 7 days, 154 stages) and the done-when (combined under 10 slot hours 7
days after merge), and end with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Write the
body as one line per paragraph (GitHub renders every newline). Create with
`mcp__github__create_pull_request` (owner `TEAMSchools`, repo `teamster`, base
`main`, head `cbini/perf/claude-resolver-score-anchors`). Read the returned
title and body back and confirm they match.

- [ ] **Step 4: Watch CI and review**

Invoke `pr-ci-review`. dbt Cloud CI builds `state:modified+`, which here is the
new model, the resolver, `fct_assessment_scores_enrollment_scoped`, and their
descendants. Expect the resolver's five unit tests and the new model's two to
run there. Invoke `superpowers:receiving-code-review` before acting on any
`claude-review` finding.

---

### Task 5: Cost check, 7 days after merge

**Files:** none. Result goes as a comment on #5261.

- [ ] **Step 1: Run the same ranking query as the measurement**

Through `mcp__bigquery__execute_sql`:

```sql
select
    regexp_extract(query, r'"node_id": "([^"]+)"') as node_id,
    count(*) as n_builds,
    round(sum(total_slot_ms) / 3600000, 2) as slot_hours_7d,
    round(avg(total_slot_ms) / 60000, 2) as avg_slot_min_per_build,
    round(avg(array_length(job_stages)), 0) as avg_stages,
from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
where
    creation_time >= timestamp_sub(current_timestamp(), interval 7 day)
    and query like '%"target_name": "prod"%'
    and statement_type = 'CREATE_TABLE_AS_SELECT'
    and (
        query like '%"node_id": "model.kipptaf.int_assessments__score_anchors"%'
        or query like '%"node_id": "model.kipptaf.int_assessments__resolved_section_enrollments"%'
    )
group by node_id
```

- [ ] **Step 2: Compare to baseline and close or follow up**

Baseline: resolver alone 15.15 slot hours, 154 stages. If the two rows sum under
10, comment the table on #5261 and close it. If not, comment the table and open
a new issue under #5212 for materializing `int_amplify__all_assessments` and
`int_assessments__assessments_canonical`, quoting the post-split stage count and
slot hours.
