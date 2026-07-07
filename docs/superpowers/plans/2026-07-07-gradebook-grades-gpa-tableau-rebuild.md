# Gradebook grades/GPA Tableau rebuild — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `rpt_tableau__student_course_grades` and
`rpt_tableau__gpa_cumulative_year` — the two Tableau extract views for the
rebuilt gradebook dashboard, decoupled from the audit lineage.

**Architecture:** Two new kipptaf view models in `models/extracts/tableau/`,
assembled directly from existing merged intermediates (Approach A from the
spec). Main view = student x term x course x category, current + prior academic
year. Companion = student x academic year over
`int_powerschool__gpa_cumulative_year`. Spec:
`docs/superpowers/specs/2026-07-07-gradebook-grades-gpa-tableau-rebuild-design.md`.

**Tech Stack:** dbt (BigQuery), kipptaf project, sqlfluff/trunk, dbt Cloud CI.

## Global Constraints

- Branch: `anthonygwalters/feat/claude-gradebook-grades-rebuild` (main repo
  checkout, not a worktree). Draft PR #4341, issue #4340.
- **Hard dependency: PR #4316 must be merged and its model materialized in prod
  before Task 2** (Task 1 verifies). The main view refs
  `int_powerschool__gpa_term_lookback`, which exists only on that branch until
  merged.
- All dbt commands run from the repo root with `--project-dir src/dbt/kipptaf`.
  Dev builds use `--target dev --defer --state target/prod` (path relative to
  project dir).
- Never run `dbt build/run --target prod` (classifier-blocked; Dagster
  materializes post-merge).
- **Miami is hard-excluded from both views.** Paterson is excluded with a
  `TODO(#4340)` pointer — its gradebook sources had zero rows on 2026-07-07
  (Task 1 re-checks).
- SQL follows `.trunk/config/.sqlfluff` plus the repo readability rules (max 1
  level of function nesting, no `QUALIFY`, no subqueries against tables/CTEs,
  ST06 column ordering). Do not run `trunk fmt` manually — the pre-commit hook
  formats.
- BigQuery validation queries run via the BigQuery MCP (SELECT-only) against the
  dev schema `zz_anthonygwalters_kipptaf_tableau` (dev builds land there) and
  prod `kipptaf_*` datasets.
- No dbt unit tests for these views: mocking would require fixtures for 8+ refs
  per model; correctness is covered by contract enforcement, uniqueness tests,
  and the Task 3/5 validation queries against real data.

---

### Task 1: Preflight gates

**Files:** none created; refreshes `src/dbt/kipptaf/target/prod/` manifest.

**Interfaces:**

- Produces: a merged-`main` branch state where
  `int_powerschool__gpa_term_lookback` resolves from the prod manifest, and a
  go/no-go answer on Paterson.

- [ ] **Step 1: Verify PR #4316 is merged**

Run: `mcp__github__pull_request_read` with `method=get`, `pullNumber=4316`.
Expected: `"merged": true`. If not merged, STOP — hand back to the user; nothing
else in this plan can compile.

- [ ] **Step 2: Verify the lookback model materialized in prod**

Run (BigQuery MCP):

```sql
select count(*) as n
from `teamster-332318.kipptaf_powerschool.int_powerschool__gpa_term_lookback`
```

Expected: query succeeds (the relation exists). `n` may be small in July (new
academic year); existence is the gate, not the count. If the relation is
missing, check
`mcp__dagster__get_asset_materializations(asset_key="kipptaf/powerschool/int_powerschool__gpa_term_lookback")`
and wait for the post-merge deploy to materialize it.

- [ ] **Step 3: Merge main and refresh the prod manifest**

```bash
git fetch origin main && git merge origin/main
uv run dbt parse --target prod --project-dir src/dbt/kipptaf --target-path target/prod
```

Expected: merge clean (spec-only branch); parse completes without errors.

- [ ] **Step 4: Record the current academic year variable**

```bash
grep -n "current_academic_year" src/dbt/kippnewark/dbt_project.yml
```

Note the value (call it `AY`). All validation queries below say `AY` / `AY - 1`;
substitute the literal.

- [ ] **Step 5: Re-check the Paterson gate**

Run (BigQuery MCP):

```sql
select
  countif(_dbt_source_relation like '%kipppaterson%') as n_paterson_fg
from `teamster-332318.kipptaf_powerschool.base_powerschool__final_grades`
```

Expected as of 2026-07-07: `0` → Paterson stays excluded and the `TODO(#4340)`
comments in Task 2/4 SQL stay. If nonzero, flag to the user before proceeding —
the region filter decision reopens.

---

### Task 2: `rpt_tableau__student_course_grades` (SQL + properties yml)

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.yml`

**Interfaces:**

- Consumes: `int_extracts__student_enrollments`, `int_powerschool__terms`,
  `stg_powerschool__terms`, `int_powerschool__gpa_term`,
  `int_powerschool__gpa_cumulative`, `int_powerschool__gpa_term_lookback`,
  `base_powerschool__course_enrollments`,
  `int_extracts__student_enrollments_subjects`, `int_people__staff_roster`,
  `base_powerschool__final_grades`, `stg_powerschool__storedgrades`,
  `int_powerschool__category_grades`, macro `union_dataset_join_clause`.
- Produces: view `kipptaf_tableau.rpt_tableau__student_course_grades`, grain one
  row per (`_dbt_source_relation`, `studentid`, `academic_year`, `quarter`,
  `course_number`, `category_name_code`).

- [ ] **Step 1: Write the model SQL**

```sql
with
    term as (
        select
            _dbt_source_relation,
            schoolid,
            yearid,

            term as `quarter`,

            term_start_date as quarter_start_date,
            term_end_date as quarter_end_date,

            is_current_term as is_current_quarter,
            semester,

        from {{ ref("int_powerschool__terms") }}

        union all

        select
            _dbt_source_relation,
            schoolid,
            yearid,

            'Y1' as `quarter`,

            firstday as quarter_start_date,
            lastday as quarter_end_date,

            false as is_current_quarter,
            'S#' as semester,

        from {{ ref("stg_powerschool__terms") }}
        where isyearrec = 1
    ),

    student_roster as (
        select
            enr._dbt_source_relation,
            enr.studentid,
            enr.student_number,
            enr.student_name,
            enr.enroll_status,
            enr.cohort,
            enr.graduation_year,
            enr.gender,
            enr.ethnicity,
            enr.academic_year,
            enr.academic_year_display,
            enr.yearid,
            enr.region,
            enr.school_level_alt as school_level,
            enr.schoolid,
            enr.school,
            enr.grade_level,
            enr.advisory,
            enr.year_in_school,
            enr.year_in_network,
            enr.rn_undergrad,
            enr.is_self_contained as is_pathways,
            enr.is_out_of_district,
            enr.is_retained_year,
            enr.is_retained_ever,
            enr.student_slideback,
            enr.lunch_status,
            enr.lep_status,
            enr.gifted_and_talented,
            enr.iep_status,
            enr.is_504,
            enr.salesforce_id,
            enr.ktc_cohort,
            enr.is_counseling_services,
            enr.is_student_athlete,
            enr.ada,
            enr.ada_above_or_at_80,
            enr.hos,
            enr.school_leader,
            enr.school_leader_tableau_username,

            term.quarter,
            term.quarter_start_date,
            term.quarter_end_date,
            term.is_current_quarter,
            term.semester,

            gtq.gpa_semester,
            gtq.total_credit_hours_y1 as gpa_total_credit_hours,
            gtq.n_failing_y1 as gpa_n_failing_y1,

            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected,
            gc.cumulative_y1_gpa_projected_unweighted,
            gc.cumulative_y1_gpa_projected_s1,
            gc.cumulative_y1_gpa_projected_s1_unweighted,
            gc.core_cumulative_y1_gpa,
            gc.potential_gpa_credits_cum_projected,
            gc.potential_gpa_credits_current_year,
            gc.gpa_needed_for_cumulative_3_0,
            gc.is_cumulative_3_0_attainable,

            lb.gpa_y1_1_week_prior,
            lb.gpa_y1_2_week_prior,
            lb.gpa_y1_4_week_prior,
            lb.gpa_y1_unweighted_1_week_prior,
            lb.gpa_y1_unweighted_2_week_prior,
            lb.gpa_y1_unweighted_4_week_prior,
            lb.n_failing_y1_1_week_prior,
            lb.n_failing_y1_2_week_prior,
            lb.n_failing_y1_4_week_prior,

            enr.academic_year
            = {{ var("current_academic_year") }} as is_current_academic_year,

            if(
                term.quarter = 'Y1', gty.gpa_y1_unweighted, gtq.gpa_y1_unweighted
            ) as gpa_y1_unweighted,

            if(term.quarter = 'Y1', gty.gpa_y1, gtq.gpa_term) as gpa_for_quarter,

            if(term.quarter = 'Y1', gty.gpa_y1, gtq.gpa_y1) as gpa_y1,

        from {{ ref("int_extracts__student_enrollments") }} as enr
        inner join
            term
            on enr.schoolid = term.schoolid
            and enr.yearid = term.yearid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="term") }}
        left join
            {{ ref("int_powerschool__gpa_term") }} as gtq
            on enr.studentid = gtq.studentid
            and enr.yearid = gtq.yearid
            and enr.schoolid = gtq.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gtq") }}
            and term.quarter = gtq.term_name
            and {{ union_dataset_join_clause(left_alias="term", right_alias="gtq") }}
        left join
            {{ ref("int_powerschool__gpa_term") }} as gty
            on enr.studentid = gty.studentid
            and enr.yearid = gty.yearid
            and enr.schoolid = gty.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gty") }}
            and gty.is_current
        /* gc join gated to the current year in ON: prior-year rows keep NULL
           cumulative/needed columns (as-of-today measures) */
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on enr.studentid = gc.studentid
            and enr.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="gc") }}
            and enr.academic_year = {{ var("current_academic_year") }}
        /* lookback is current-year only by construction (yearid in the join
           key), so prior-year rows read NULL naturally */
        left join
            {{ ref("int_powerschool__gpa_term_lookback") }} as lb
            on enr.studentid = lb.studentid
            and enr.schoolid = lb.schoolid
            and enr.yearid = lb.yearid
            and {{ union_dataset_join_clause(left_alias="enr", right_alias="lb") }}
        where
            enr.rn_year = 1
            and not enr.is_out_of_district
            and enr.enroll_status != -1
            and enr.academic_year >= {{ var("current_academic_year") - 1 }}
            /* Miami hard-excluded: region unsupported in the rebuilt
               dashboard (#4340) */
            -- TODO(#4340): add Paterson once PS gradebook data is populated
            and enr.region in ('Newark', 'Camden')
    ),

    course_enrollments as (
        select
            m._dbt_source_relation,
            m.cc_studentid as studentid,
            m.cc_yearid as yearid,
            m.cc_course_number as course_number,
            m.cc_sectionid as sectionid,
            m.cc_dateenrolled as date_enrolled,
            m.sections_dcid,
            m.sections_section_number as section_number,
            m.sections_external_expression as external_expression,
            m.courses_credittype as credit_type,
            m.courses_course_name as course_name,
            m.courses_excludefromgpa as exclude_from_gpa,
            m.teachernumber as teacher_number,
            m.teacher_lastfirst as teacher_name,

            f.is_tutoring as tutoring_nj,
            f.nj_student_tier,

            r.sam_account_name as teacher_tableau_username,
        from {{ ref("base_powerschool__course_enrollments") }} as m
        left join
            {{ ref("int_extracts__student_enrollments_subjects") }} as f
            on m.cc_studentid = f.studentid
            and m.cc_academic_year = f.academic_year
            and m.courses_credittype = f.powerschool_credittype
            and {{ union_dataset_join_clause(left_alias="m", right_alias="f") }}
            and f.rn_year = 1
        left join
            {{ ref("int_people__staff_roster") }} as r
            on m.teachernumber = r.powerschool_teacher_number
        where
            m.rn_course_number_year = 1
            and m.cc_sectionid > 0
            and m.cc_course_number not in (
                'LOG100',  -- Lunch
                'LOG1010',  -- Lunch
                'LOG11',  -- Lunch
                'LOG12',  -- Lunch
                'LOG20',  -- Early Dismissal
                'LOG22999XL',  -- Lunch
                'LOG300',  -- Study Hall
                'LOG9',  -- Lunch
                'SEM22106G1',  -- Advisory
                'SEM22106S1'  -- Not in SY24-25 yet
            )
    ),

    y1_final_grades as (
        select
            _dbt_source_relation,
            studentid,
            yearid,
            course_number,
            storecode,

            cast(`percent` as float64) as y1_course_final_percent_grade_adjusted,

            grade as y1_course_final_letter_grade_adjusted,
            earnedcrhrs as y1_course_final_earned_credits,
            potentialcrhrs as y1_course_final_potential_credit_hours,
            gpa_points as y1_course_final_grade_points,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1'
            and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    quarter_grades as (
        /* current year: live gradebook */
        select
            _dbt_source_relation,
            studentid,
            yearid,
            course_number,

            storecode as `quarter`,

            term_percent_grade_adjusted as quarter_course_percent_grade,
            term_letter_grade_adjusted as quarter_course_letter_grade,
            term_grade_points as quarter_course_grade_points,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and not is_dropped_section
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')

        union all

        /* current year: in-progress Y1 row */
        select
            _dbt_source_relation,
            studentid,
            yearid,
            course_number,

            'Y1' as `quarter`,

            y1_percent_grade_adjusted as quarter_course_percent_grade,
            y1_letter_grade_adjusted as quarter_course_letter_grade,
            y1_grade_points as quarter_course_grade_points,
            y1_percent_grade_adjusted as y1_course_in_progress_percent_grade_adjusted,
            y1_letter_grade_adjusted as y1_course_in_progress_letter_grade_adjusted,
            y1_grade_points as y1_course_in_progress_grade_points,
            y1_grade_points_unweighted as y1_course_in_progress_grade_points_unweighted,

            need_60,
            need_70,
            need_80,
            need_90,

        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and termbin_is_current
            and not is_dropped_section

        union all

        /* prior year: stored grades (Q1-Q4 term rows plus the stored Y1 row,
           which fills the quarter columns on Y1 rows like the in-progress
           branch does for the current year) */
        select
            _dbt_source_relation,
            studentid,
            yearid,
            course_number,

            storecode as `quarter`,

            cast(`percent` as float64) as quarter_course_percent_grade,
            grade as quarter_course_letter_grade,
            gpa_points as quarter_course_grade_points,

            cast(null as float64) as y1_course_in_progress_percent_grade_adjusted,
            cast(null as string) as y1_course_in_progress_letter_grade_adjusted,
            cast(null as float64) as y1_course_in_progress_grade_points,
            cast(null as float64) as y1_course_in_progress_grade_points_unweighted,

            cast(null as float64) as need_60,
            cast(null as float64) as need_70,
            cast(null as float64) as need_80,
            cast(null as float64) as need_90,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode in ('Q1', 'Q2', 'Q3', 'Q4', 'Y1')
            and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    category_grades as (
        select
            _dbt_source_relation,
            yearid,
            schoolid,
            studentid,
            course_number,
            sectionid,
            storecode_type as category_name_code,
            storecode as category_quarter_code,
            percent_grade as category_quarter_percent_grade,
            percent_grade_y1_running as category_y1_percent_grade_running,

            concat('Q', storecode_order) as term,

            avg(if(is_current, percent_grade_y1_running, null)) over (
                partition by
                    _dbt_source_relation,
                    studentid,
                    yearid,
                    course_number,
                    storecode_type
            ) as category_y1_percent_grade_current,

            round(
                avg(percent_grade) over (
                    partition by _dbt_source_relation, yearid, studentid, storecode
                ),
                2
            ) as category_quarter_average_all_courses,

        from {{ ref("int_powerschool__category_grades") }}
        where
            yearid >= {{ var("current_academic_year") - 1991 }}
            and not is_dropped_section
            and storecode_type not in ('Q')
            and termbin_start_date <= current_date('{{ var("local_timezone") }}')
    )

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.salesforce_id,
    s.ktc_cohort,
    s.enroll_status,
    s.cohort,
    s.graduation_year,
    s.gender,
    s.ethnicity,
    s.advisory,
    s.hos,
    s.school_leader,
    s.school_leader_tableau_username,
    s.year_in_school,
    s.year_in_network,
    s.rn_undergrad,
    s.is_out_of_district,
    s.is_pathways,
    s.is_retained_year,
    s.is_retained_ever,
    s.student_slideback,
    s.lunch_status,
    s.gifted_and_talented,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.ada,
    s.ada_above_or_at_80,

    s.`quarter`,
    s.semester,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,
    s.is_current_academic_year,

    s.gpa_for_quarter,
    s.gpa_semester,
    s.gpa_y1,
    s.gpa_y1_unweighted,
    s.gpa_total_credit_hours,
    s.gpa_n_failing_y1,

    s.gpa_y1_1_week_prior,
    s.gpa_y1_2_week_prior,
    s.gpa_y1_4_week_prior,
    s.gpa_y1_unweighted_1_week_prior,
    s.gpa_y1_unweighted_2_week_prior,
    s.gpa_y1_unweighted_4_week_prior,
    s.n_failing_y1_1_week_prior,
    s.n_failing_y1_2_week_prior,
    s.n_failing_y1_4_week_prior,

    s.cumulative_y1_gpa,
    s.cumulative_y1_gpa_unweighted,
    s.cumulative_y1_gpa_projected,
    s.cumulative_y1_gpa_projected_unweighted,
    s.cumulative_y1_gpa_projected_s1,
    s.cumulative_y1_gpa_projected_s1_unweighted,
    s.core_cumulative_y1_gpa,
    s.potential_gpa_credits_cum_projected,
    s.potential_gpa_credits_current_year,
    s.gpa_needed_for_cumulative_3_0,
    s.is_cumulative_3_0_attainable,

    ce.sectionid,
    ce.sections_dcid,
    ce.section_number,
    ce.external_expression,
    ce.date_enrolled,
    ce.credit_type,
    ce.course_number,
    ce.course_name,
    ce.exclude_from_gpa,
    ce.teacher_number,
    ce.teacher_name,
    ce.teacher_tableau_username,
    ce.tutoring_nj,
    ce.nj_student_tier,

    y1f.y1_course_final_percent_grade_adjusted,
    y1f.y1_course_final_letter_grade_adjusted,
    y1f.y1_course_final_earned_credits,
    y1f.y1_course_final_potential_credit_hours,
    y1f.y1_course_final_grade_points,

    qg.quarter_course_percent_grade,
    qg.quarter_course_letter_grade,
    qg.quarter_course_grade_points,
    qg.y1_course_in_progress_percent_grade_adjusted,
    qg.y1_course_in_progress_letter_grade_adjusted,
    qg.y1_course_in_progress_grade_points,
    qg.y1_course_in_progress_grade_points_unweighted,
    qg.need_60,
    qg.need_70,
    qg.need_80,
    qg.need_90,

    c.category_name_code,
    c.category_quarter_code,
    c.category_quarter_percent_grade,
    c.category_y1_percent_grade_running,
    c.category_y1_percent_grade_current,
    c.category_quarter_average_all_courses,

    if(
        s.grade_level < 9, ce.section_number, ce.external_expression
    ) as section_or_period,

from student_roster as s
left join
    course_enrollments as ce
    on s.studentid = ce.studentid
    and s.yearid = ce.yearid
    and {{ union_dataset_join_clause(left_alias="s", right_alias="ce") }}
left join
    y1_final_grades as y1f
    on s.studentid = y1f.studentid
    and s.yearid = y1f.yearid
    and s.`quarter` = y1f.storecode
    and {{ union_dataset_join_clause(left_alias="s", right_alias="y1f") }}
    and ce.course_number = y1f.course_number
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="y1f") }}
left join
    quarter_grades as qg
    on s.studentid = qg.studentid
    and s.yearid = qg.yearid
    and s.`quarter` = qg.`quarter`
    and {{ union_dataset_join_clause(left_alias="s", right_alias="qg") }}
    and ce.course_number = qg.course_number
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="qg") }}
left join
    category_grades as c
    on s.studentid = c.studentid
    and s.yearid = c.yearid
    and s.`quarter` = c.term
    and {{ union_dataset_join_clause(left_alias="s", right_alias="c") }}
    and ce.sectionid = c.sectionid
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="c") }}
where s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
```

Implementation notes (read before writing):

- `quarter_grades` joins on `course_number` (not `sectionid`) — matches how the
  old model joined its Y1-historical branch, works for the storedgrades branch
  (transfer grades carry `sectionid <= 0`), and is safe because
  `course_enrollments` is deduped to `rn_course_number_year = 1` (one row per
  student x year x course_number).
- `gty.is_current` is **within-year** (verified 2026-07-07: yearid 34's Q4 row
  has `is_current = true`), so the Y1-row join needs no prior-year special case.
- `yearid >= {{ var("current_academic_year") - 1991 }}` is `(AY - 1) - 1990` —
  the prior year's PowerSchool yearid.

- [ ] **Step 2: Write the properties yml**

Uniqueness severity stays project-default (`warn`): storedgrades carries a known
frozen duplicate corpus (#3900), and Task 3 adjudicates any real violations
before ship.

```yaml
models:
  - name: rpt_tableau__student_course_grades
    description: >-
      Grades and GPA extract for the rebuilt gradebook Tableau dashboard — one
      row per student, term, course, and gradebook category for the current and
      prior academic year. Decoupled from the gradebook-audit lineage: no
      assignment-level data, audit flags, comments, or citizenship.
      Student-grain as-of-today measures (cumulative GPA, needed-GPA, 1/2/4-week
      lookbacks) populate current-year rows only. Newark and Camden only — Miami
      is hard-excluded (region unsupported in the rebuilt dashboard) and
      Paterson is pending gradebook data (TODO(#4340)).
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - _dbt_source_relation
              - studentid
              - academic_year
              - quarter
              - course_number
              - category_name_code
    columns:
      - name: _dbt_source_relation
        data_type: string
        description: Source relation identifier from dbt_utils.union_relations.
      - name: academic_year
        data_type: int64
        description: Academic year, start-year convention (2025 = SY25-26).
      - name: academic_year_display
        data_type: string
        description: Display form of the academic year (e.g. 2025-26).
      - name: region
        data_type: string
        description: District region (Newark or Camden; see model description).
      - name: school_level
        data_type: string
        description: School level (ES/MS/HS) from the year's enrollment.
      - name: schoolid
        data_type: int64
        description: School_Number of the year's primary enrollment school.
      - name: school
        data_type: string
        description: School name.
      - name: studentid
        data_type: int64
        description:
          The internal number and ID of the associated Students record.
      - name: student_number
        data_type: int64
        description: District student number.
      - name: student_name
        data_type: string
        description: Student full name (last, first).
      - name: grade_level
        data_type: int64
        description: Grade level in the row's academic year.
      - name: salesforce_id
        data_type: string
        description: KIPP Forward Salesforce contact id.
      - name: ktc_cohort
        data_type: int64
        description: KIPP Through College cohort year.
      - name: enroll_status
        data_type: int64
        description:
          Current PowerSchool enroll_status (student-level, not per-year).
      - name: cohort
        data_type: int64
        description: Graduation cohort year.
      - name: graduation_year
        data_type: int64
        description: Expected graduation year.
      - name: gender
        data_type: string
        description: Student gender code.
      - name: ethnicity
        data_type: string
        description: Student ethnicity code.
      - name: advisory
        data_type: string
        description: Advisory/homeroom name for the year.
      - name: hos
        data_type: string
        description: Head of school name.
      - name: school_leader
        data_type: string
        description: School leader name.
      - name: school_leader_tableau_username
        data_type: string
        description: School leader Tableau username (row-level security).
      - name: year_in_school
        data_type: int64
        description: Number of years enrolled at the school.
      - name: year_in_network
        data_type: int64
        description: Number of years enrolled in the network.
      - name: rn_undergrad
        data_type: int64
        description: Row number over undergrad enrollments (1 = most recent).
      - name: is_out_of_district
        data_type: boolean
        description:
          Out-of-district placement flag (always false here; filtered).
      - name: is_pathways
        data_type: boolean
        description: Self-contained (Pathways) program flag.
      - name: is_retained_year
        data_type: boolean
        description: Retained in the row's academic year.
      - name: is_retained_ever
        data_type: boolean
        description: Ever retained.
      - name: student_slideback
        data_type: boolean
        description: Student slideback flag from enrollment reporting.
      - name: lunch_status
        data_type: string
        description: Free/reduced lunch status code.
      - name: gifted_and_talented
        data_type: string
        description: Gifted and talented status.
      - name: iep_status
        data_type: string
        description: IEP status label.
      - name: lep_status
        data_type: boolean
        description: English learner status.
      - name: is_504
        data_type: boolean
        description: Section 504 plan flag.
      - name: is_counseling_services
        data_type: int64
        description: Counseling services flag.
      - name: is_student_athlete
        data_type: int64
        description: Student athlete flag.
      - name: ada
        data_type: float64
        description: Average daily attendance for the year.
      - name: ada_above_or_at_80
        data_type: boolean
        description: ADA at or above 80 percent.
      - name: quarter
        data_type: string
        quote: true
        description: Reporting term (Q1-Q4) or Y1 for the year row.
      - name: semester
        data_type: string
        description: Semester of the term (S1/S2; S# on Y1 rows).
      - name: quarter_start_date
        data_type: date
        description: Term start date.
      - name: quarter_end_date
        data_type: date
        description: Term end date.
      - name: is_current_quarter
        data_type: boolean
        description: Term is the school's current term (false on Y1 rows).
      - name: is_current_academic_year
        data_type: boolean
        description: >-
          Row belongs to the current academic year. False marks prior-year rows,
          where every as-of-today column group (cumulative, needed-GPA,
          lookback, need_*, in-progress Y1) is NULL by construction.
      - name: gpa_for_quarter
        data_type: float64
        description: Term GPA for the row's term (Y1 GPA on Y1 rows).
      - name: gpa_semester
        data_type: float64
        description: Semester GPA for the row's term.
      - name: gpa_y1
        data_type: float64
        description: Y1 GPA as of the row's term.
      - name: gpa_y1_unweighted
        data_type: float64
        description: Unweighted Y1 GPA as of the row's term.
      - name: gpa_total_credit_hours
        data_type: float64
        description: Total Y1 GPA credit hours for the year.
      - name: gpa_n_failing_y1
        data_type: int64
        description: Count of failing Y1 grades as of the row's term.
      - name: gpa_y1_1_week_prior
        data_type: float64
        description: >-
          Weighted Y1 GPA in effect 7 days ago (current-year rows only; NULL
          when the boundary predates the year's first snapshot version).
      - name: gpa_y1_2_week_prior
        data_type: float64
        description:
          Weighted Y1 GPA in effect 14 days ago (current-year rows only).
      - name: gpa_y1_4_week_prior
        data_type: float64
        description:
          Weighted Y1 GPA in effect 28 days ago (current-year rows only).
      - name: gpa_y1_unweighted_1_week_prior
        data_type: float64
        description:
          Unweighted Y1 GPA in effect 7 days ago (current-year rows only).
      - name: gpa_y1_unweighted_2_week_prior
        data_type: float64
        description:
          Unweighted Y1 GPA in effect 14 days ago (current-year rows only).
      - name: gpa_y1_unweighted_4_week_prior
        data_type: float64
        description:
          Unweighted Y1 GPA in effect 28 days ago (current-year rows only).
      - name: n_failing_y1_1_week_prior
        data_type: int64
        description: Failing Y1 grade count 7 days ago (current-year rows only).
      - name: n_failing_y1_2_week_prior
        data_type: int64
        description:
          Failing Y1 grade count 14 days ago (current-year rows only).
      - name: n_failing_y1_4_week_prior
        data_type: int64
        description:
          Failing Y1 grade count 28 days ago (current-year rows only).
      - name: cumulative_y1_gpa
        data_type: float64
        description: Cumulative weighted Y1 GPA (current-year rows only).
      - name: cumulative_y1_gpa_unweighted
        data_type: float64
        description: Cumulative unweighted Y1 GPA (current-year rows only).
      - name: cumulative_y1_gpa_projected
        data_type: float64
        description:
          Projected cumulative weighted Y1 GPA (current-year rows only).
      - name: cumulative_y1_gpa_projected_unweighted
        data_type: float64
        description:
          Projected cumulative unweighted Y1 GPA (current-year rows only).
      - name: cumulative_y1_gpa_projected_s1
        data_type: float64
        description:
          S1-basis projected cumulative Y1 GPA (current-year rows only).
      - name: cumulative_y1_gpa_projected_s1_unweighted
        data_type: float64
        description: >-
          S1-basis projected cumulative unweighted Y1 GPA (current-year rows
          only).
      - name: core_cumulative_y1_gpa
        data_type: float64
        description:
          Cumulative Y1 GPA over core courses (current-year rows only).
      - name: potential_gpa_credits_cum_projected
        data_type: float64
        description: >-
          Cumulative potential GPA credit hours including in-progress
          current-year courses (current-year rows only).
      - name: potential_gpa_credits_current_year
        data_type: float64
        description: >-
          Potential GPA credit hours enrolled this year (current-year rows
          only).
      - name: gpa_needed_for_cumulative_3_0
        data_type: float64
        description: >-
          Weighted Y1 GPA needed across current-year GPA credits to finish with
          a 3.00 projected cumulative (current-year rows only; negative means
          already guaranteed).
      - name: is_cumulative_3_0_attainable
        data_type: boolean
        description: >-
          True when `gpa_needed_for_cumulative_3_0` is at or below the
          credit-weighted max achievable this year (current-year rows only).
      - name: sectionid
        data_type: int64
        description: PowerSchool section id of the course enrollment.
      - name: sections_dcid
        data_type: int64
        description: PowerSchool sections DCID.
      - name: section_number
        data_type: string
        description: Section number.
      - name: external_expression
        data_type: string
        description: Section period expression (HS scheduling).
      - name: date_enrolled
        data_type: date
        description: Course enrollment start date.
      - name: credit_type
        data_type: string
        description: Course credit type (subject area).
      - name: course_number
        data_type: string
        description: Course number.
      - name: course_name
        data_type: string
        description: Course name.
      - name: exclude_from_gpa
        data_type: int64
        description: Course excluded from GPA (1) or included (0).
      - name: teacher_number
        data_type: string
        description: Teacher number of the section's teacher.
      - name: teacher_name
        data_type: string
        description: Teacher name (last, first).
      - name: teacher_tableau_username
        data_type: string
        description: Teacher Tableau username (row-level security).
      - name: tutoring_nj
        data_type: boolean
        description:
          NJ tutoring program flag for the subject (NULL outside NJ scope).
      - name: nj_student_tier
        data_type: string
        description: NJ student tier for the subject.
      - name: y1_course_final_percent_grade_adjusted
        data_type: float64
        description: Final stored Y1 percent grade (Y1 rows only).
      - name: y1_course_final_letter_grade_adjusted
        data_type: string
        description: Final stored Y1 letter grade (Y1 rows only).
      - name: y1_course_final_earned_credits
        data_type: float64
        description: Credits earned for the course (Y1 rows only).
      - name: y1_course_final_potential_credit_hours
        data_type: float64
        description: Potential credit hours for the course (Y1 rows only).
      - name: y1_course_final_grade_points
        data_type: float64
        description: Final stored Y1 grade points (Y1 rows only).
      - name: quarter_course_percent_grade
        data_type: float64
        description: >-
          Course percent grade for the row's term. Y1 rows carry the in-progress
          (current year) or stored (prior year) Y1 percent.
      - name: quarter_course_letter_grade
        data_type: string
        description: Course letter grade for the row's term.
      - name: quarter_course_grade_points
        data_type: float64
        description: Course grade points for the row's term.
      - name: y1_course_in_progress_percent_grade_adjusted
        data_type: float64
        description: In-progress Y1 percent grade (current-year rows only).
      - name: y1_course_in_progress_letter_grade_adjusted
        data_type: string
        description: In-progress Y1 letter grade (current-year rows only).
      - name: y1_course_in_progress_grade_points
        data_type: float64
        description: In-progress Y1 grade points (current-year rows only).
      - name: y1_course_in_progress_grade_points_unweighted
        data_type: float64
        description: >-
          In-progress unweighted Y1 grade points (current-year rows only).
      - name: need_60
        data_type: float64
        description: >-
          Percent needed on remaining work to reach a 60 course grade
          (current-year rows only).
      - name: need_70
        data_type: float64
        description: Percent needed to reach a 70 (current-year rows only).
      - name: need_80
        data_type: float64
        description: Percent needed to reach an 80 (current-year rows only).
      - name: need_90
        data_type: float64
        description: Percent needed to reach a 90 (current-year rows only).
      - name: category_name_code
        data_type: string
        description: Gradebook category code (e.g. F/S/W; NULL on Y1 rows).
      - name: category_quarter_code
        data_type: string
        description: Category term code (e.g. Q1).
      - name: category_quarter_percent_grade
        data_type: float64
        description: Category percent grade for the term.
      - name: category_y1_percent_grade_running
        data_type: float64
        description: Running Y1 category percent grade through the term.
      - name: category_y1_percent_grade_current
        data_type: float64
        description: >-
          Y1 running category percent as of the current term (current-year rows
          only).
      - name: category_quarter_average_all_courses
        data_type: float64
        description: >-
          Student's average percent across all courses for the category-term.
      - name: section_or_period
        data_type: string
        description: >-
          Section number below grade 9, period expression at grade 9 and above.
```

- [ ] **Step 3: Parse and compile**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf
uv run dbt compile --select rpt_tableau__student_course_grades \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: parse and compile succeed; open the compiled SQL under
`src/dbt/kipptaf/target/compiled/` and eyeball that every `ref` resolved
(deferred refs point at prod `kipptaf_*` datasets).

- [ ] **Step 4: Dev build with tests**

```bash
uv run dbt build --select rpt_tableau__student_course_grades \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: model builds a view in `zz_anthonygwalters_kipptaf_tableau`;
uniqueness test runs (PASS or WARN — a WARN routes to Task 3 Step 2
adjudication, not an automatic fix).

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.yml
git commit -m "feat(kipptaf): add rpt_tableau__student_course_grades extract

Refs #4340

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Main view validation

**Files:** none (BigQuery MCP queries against the dev view). Substitute `AY`
from Task 1 Step 4.

**Interfaces:**

- Consumes: dev view
  `zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`.
- Produces: validated grain + parity, and the extract-size numbers for the user
  decision.

- [ ] **Step 1: Row count by year (extract-size decision input)**

```sql
select
  academic_year,
  count(*) as row_count,
  count(distinct student_number) as n_students,
  countif(category_name_code is not null) as rows_with_category
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
group by academic_year
order by academic_year
```

Expected: two years only (AY and AY-1); zero Miami/Paterson rows implied by
Step 3. Record totals — they go verbatim into the Task 6 report for the user's
2-year / course-grain-prior / 1-year decision.

- [ ] **Step 2: Uniqueness adjudication (only if the Task 2 test WARNed)**

```sql
select
  _dbt_source_relation,
  studentid,
  academic_year,
  `quarter`,
  course_number,
  category_name_code,
  count(*) as n
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
group by 1, 2, 3, 4, 5, 6
having count(*) > 1
order by n desc
limit 20
```

Adjudication rule: duplicates tracing to the frozen storedgrades double-write
corpus (#3900 — same student/course, prior-year rows) are acceptable at `warn`;
annotate the yml test with a
`# TODO(#3915): returns to error when source cleanup completes` comment. Any
other duplicate shape is a join bug — fix before proceeding (do NOT add dedupe;
find the fan-out).

- [ ] **Step 3: Region and NULL-semantics spot checks**

```sql
select
  region,
  is_current_academic_year,
  countif(cumulative_y1_gpa is not null) as n_cum,
  countif(gpa_y1_1_week_prior is not null) as n_lookback,
  countif(need_70 is not null) as n_need,
  countif(quarter_course_percent_grade is not null) as n_qtr_grade
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
group by region, is_current_academic_year
order by region, is_current_academic_year
```

Expected: regions are exactly Newark and Camden. On
`is_current_academic_year = false` rows: `n_cum = 0`, `n_lookback = 0`,
`n_need = 0`, and `n_qtr_grade > 0` (stored grades populate). On current rows in
July, grade counts may be near zero (new year) — that is not a failure.

- [ ] **Step 4: Parity against upstream intermediates (prior year)**

```sql
select
  'new_view' as src,
  count(distinct student_number) as n_students,
  round(avg(gpa_y1), 4) as avg_gpa_y1
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
where academic_year = 2025 and `quarter` = 'Y1'
union all
select
  'gpa_term',
  count(distinct gt.studentid),
  round(avg(gt.gpa_y1), 4)
from `teamster-332318.kipptaf_powerschool.int_powerschool__gpa_term` as gt
where
  gt.yearid = 35
  and gt.is_current
  and gt._dbt_source_relation not like '%kippmiami%'
```

(Adjust the literals to `AY - 1` / `AY - 1991` if AY has rolled past 2026.)
Expected: `avg_gpa_y1` matches within rounding; student counts differ only by
the roster filters (enroll_status, out-of-district) — investigate gaps over ~2%.

---

### Task 4: `rpt_tableau__gpa_cumulative_year` (SQL + properties yml)

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.yml`

**Interfaces:**

- Consumes: `int_powerschool__gpa_cumulative_year`,
  `int_extracts__student_enrollments`, macro `union_dataset_join_clause`.
- Produces: view `kipptaf_tableau.rpt_tableau__gpa_cumulative_year`, one row per
  (`student_number`, `academic_year`), Tableau-related to the main view on
  `student_number`.

- [ ] **Step 1: Write the model SQL**

```sql
select
    gcy._dbt_source_relation,
    gcy._dbt_source_project,
    gcy.studentid,
    gcy.academic_year,
    gcy.schoolid,
    gcy.grade_level,
    gcy.is_projected,
    gcy.earned_credits_cum,
    gcy.potential_gpa_credits_cum,
    gcy.cumulative_y1_gpa,
    gcy.cumulative_y1_gpa_unweighted,

    e.student_number,
    e.student_name,
    e.academic_year_display,
    e.region,
    e.school_level_alt as school_level,
    e.school,
    e.enroll_status,
    e.cohort,
    e.graduation_year,
    e.gender,
    e.ethnicity,
    e.advisory,
    e.year_in_school,
    e.year_in_network,
    e.rn_undergrad,
    e.is_self_contained as is_pathways,
    e.is_retained_year,
    e.is_retained_ever,
    e.student_slideback,
    e.lunch_status,
    e.lep_status,
    e.gifted_and_talented,
    e.iep_status,
    e.is_504,
    e.salesforce_id,
    e.ktc_cohort,
    e.is_counseling_services,
    e.is_student_athlete,
    e.ada,
    e.ada_above_or_at_80,
    e.hos,
    e.school_leader,
    e.school_leader_tableau_username,

from {{ ref("int_powerschool__gpa_cumulative_year") }} as gcy
/* the inner join on the year's rn_year = 1 enrollment (including schoolid)
   dedupes the union model's student x school x year grain to one row per
   student-year, keyed to the primary enrollment school */
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on gcy.studentid = e.studentid
    and gcy.academic_year = e.academic_year
    and gcy.schoolid = e.schoolid
    and {{ union_dataset_join_clause(left_alias="gcy", right_alias="e") }}
where
    e.rn_year = 1
    and not e.is_out_of_district
    and e.enroll_status in (0, 3)
    /* Miami hard-excluded: region unsupported in the rebuilt dashboard
       (#4340) */
    and e.region != 'Miami'
```

- [ ] **Step 2: Write the properties yml**

```yaml
models:
  - name: rpt_tableau__gpa_cumulative_year
    description: >-
      Year-grain cumulative GPA companion for the rebuilt gradebook Tableau
      dashboard — one row per student and academic year with cumulative Y1 GPA
      as of the end of that year, joined to that year's enrollment attributes
      (demographics are as-of-that-year, not current). The current-year row is
      the projected row (is_projected = true) and matches the main extract's
      projected cumulative columns exactly. Related to
      rpt_tableau__student_course_grades in Tableau on student_number. Miami
      hard-excluded.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - academic_year
    columns:
      - name: _dbt_source_relation
        data_type: string
        description: Source relation identifier from dbt_utils.union_relations.
      - name: _dbt_source_project
        data_type: string
        description: District code location derived from `_dbt_source_relation`.
      - name: studentid
        data_type: int64
        description:
          The internal number and ID of the associated Students record.
      - name: academic_year
        data_type: int64
        description: Academic year, start-year convention (2025 = SY25-26).
      - name: schoolid
        data_type: int64
        description: School_Number of the year's primary enrollment school.
      - name: grade_level
        data_type: int64
        description: Grade level in that academic year.
      - name: is_projected
        data_type: boolean
        description: >-
          False for completed years recomputed from stored grades; true for the
          current-year row sourced from projected values.
      - name: earned_credits_cum
        data_type: float64
        description: >-
          Running earned credit hours through this academic year
          (graduation-credit basis).
      - name: potential_gpa_credits_cum
        data_type: float64
        description: >-
          Running potential GPA credit hours through this academic year — the
          cumulative GPA denominator.
      - name: cumulative_y1_gpa
        data_type: float64
        description: Cumulative weighted Y1 GPA through this academic year.
      - name: cumulative_y1_gpa_unweighted
        data_type: float64
        description: Cumulative unweighted Y1 GPA through this academic year.
      - name: student_number
        data_type: int64
        description: District student number (Tableau relationship key).
      - name: student_name
        data_type: string
        description: Student full name (last, first).
      - name: academic_year_display
        data_type: string
        description: Display form of the academic year (e.g. 2025-26).
      - name: region
        data_type: string
        description: District region in that year (Newark/Camden/Paterson).
      - name: school_level
        data_type: string
        description: School level (ES/MS/HS) in that year.
      - name: school
        data_type: string
        description: School name in that year.
      - name: enroll_status
        data_type: int64
        description: Current PowerSchool enroll_status (0 active, 3 graduated).
      - name: cohort
        data_type: int64
        description: Graduation cohort year.
      - name: graduation_year
        data_type: int64
        description: Expected graduation year.
      - name: gender
        data_type: string
        description: Student gender code.
      - name: ethnicity
        data_type: string
        description: Student ethnicity code.
      - name: advisory
        data_type: string
        description: Advisory/homeroom name in that year.
      - name: year_in_school
        data_type: int64
        description: Years enrolled at the school as of that year.
      - name: year_in_network
        data_type: int64
        description: Years enrolled in the network as of that year.
      - name: rn_undergrad
        data_type: int64
        description: Row number over undergrad enrollments (1 = most recent).
      - name: is_pathways
        data_type: boolean
        description: Self-contained (Pathways) program flag in that year.
      - name: is_retained_year
        data_type: boolean
        description: Retained in that academic year.
      - name: is_retained_ever
        data_type: boolean
        description: Ever retained as of that year.
      - name: student_slideback
        data_type: boolean
        description: Student slideback flag from enrollment reporting.
      - name: lunch_status
        data_type: string
        description: Free/reduced lunch status code in that year.
      - name: lep_status
        data_type: boolean
        description: English learner status in that year.
      - name: gifted_and_talented
        data_type: string
        description: Gifted and talented status in that year.
      - name: iep_status
        data_type: string
        description: IEP status label in that year.
      - name: is_504
        data_type: boolean
        description: Section 504 plan flag in that year.
      - name: salesforce_id
        data_type: string
        description: KIPP Forward Salesforce contact id.
      - name: ktc_cohort
        data_type: int64
        description: KIPP Through College cohort year.
      - name: is_counseling_services
        data_type: int64
        description: Counseling services flag in that year.
      - name: is_student_athlete
        data_type: int64
        description: Student athlete flag in that year.
      - name: ada
        data_type: float64
        description: Average daily attendance in that year.
      - name: ada_above_or_at_80
        data_type: boolean
        description: ADA at or above 80 percent in that year.
      - name: hos
        data_type: string
        description: Head of school name in that year.
      - name: school_leader
        data_type: string
        description: School leader name in that year.
      - name: school_leader_tableau_username
        data_type: string
        description: School leader Tableau username (row-level security).
```

- [ ] **Step 3: Dev build with tests**

```bash
uv run dbt build --select rpt_tableau__gpa_cumulative_year \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state target/prod
```

Expected: view builds; uniqueness test PASS. A WARN here means duplicate
(student_number, academic_year) — most likely a same-year cross-district
transfer (two `_dbt_source_relation` values). Quantify with the Task 5 Step 2
query and stop for a user decision if any rows return; do not add dedupe
silently.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.yml
git commit -m "feat(kipptaf): add rpt_tableau__gpa_cumulative_year companion extract

Refs #4340

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Companion validation

**Files:** none (BigQuery MCP queries).

**Interfaces:**

- Consumes: dev view
  `zz_anthonygwalters_kipptaf_tableau.rpt_tableau__gpa_cumulative_year`, dev
  view `zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`,
  prod `kipptaf_powerschool.int_powerschool__gpa_cumulative_year`.

- [ ] **Step 1: Coverage — how many union student-years the join drops**

```sql
with
  source_years as (
    select distinct
      regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as district,
      studentid,
      academic_year
    from `teamster-332318.kipptaf_powerschool.int_powerschool__gpa_cumulative_year`
    where _dbt_source_relation not like '%kippmiami%'
  ),
  view_years as (
    select distinct
      regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as district,
      studentid,
      academic_year
    from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__gpa_cumulative_year`
  )
select
  count(*) as n_source,
  countif(v.studentid is not null) as n_kept
from source_years as s
left join
  view_years as v
  on s.district = v.district
  and s.studentid = v.studentid
  and s.academic_year = v.academic_year
```

Expected: `n_kept / n_source` well above 90%. Drops come from the enroll_status
filter (withdrawn students — intended) and from stored-grade years whose school
never matches an rn_year=1 enrollment. If unexplained drops exceed ~5% of
non-withdrawn students, stop and report — the schoolid join strategy reopens.

- [ ] **Step 2: PK duplicate probe (cross-district transfers)**

```sql
select student_number, academic_year, count(*) as n
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__gpa_cumulative_year`
group by student_number, academic_year
having count(*) > 1
limit 20
```

Expected: zero rows. Any rows → stop for a user decision (options: keep both
rows and re-key the test on `_dbt_source_project`, or prefer the latest
district).

- [ ] **Step 3: Tie-out to the main extract's projected columns**

```sql
select
  count(*) as n_students,
  countif(
    abs(y.cumulative_y1_gpa - g.cumulative_y1_gpa_projected) > 0.005
  ) as n_mismatch
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__gpa_cumulative_year` as y
inner join (
  select distinct student_number, cumulative_y1_gpa_projected
  from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
  where is_current_academic_year and cumulative_y1_gpa_projected is not null
) as g
  on y.student_number = g.student_number
where y.is_projected
```

Expected: `n_mismatch = 0` (spec: projected row ties out verbatim).

---

### Task 6: Lint, push, CI, and handoff report

**Files:** none created.

- [ ] **Step 1: Trunk check the four new files**

```bash
.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.yml \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.sql \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_cumulative_year.yml
```

Expected: no issues (pre-commit only formats; sqlfluff/yamllint fire here and at
pre-push).

- [ ] **Step 2: Push and watch CI on PR #4341**

```bash
git push origin anthonygwalters/feat/claude-gradebook-grades-rebuild
```

Then poll `gh api repos/TEAMSchools/teamster/commits/HEAD_SHA/status` (dbt Cloud
commit status) and `mcp__github__pull_request_read get_check_runs`
(Trunk/CodeQL). dbt Cloud CI builds `state:modified+` — expect the two new views
plus their tests only (new models, no source edits). After CI success, run
`mcp__dbt__get_job_run_error(run_id=CI_RUN, warning_only=true)` and triage
warnings (pre-existing-on-main warnings are not this PR's).

- [ ] **Step 3: Report to the user**

Deliver in one message: row counts by year from Task 3 Step 1 (the 2-year size
decision), any uniqueness adjudications, companion coverage numbers, tie-out
result, CI status, and the reminder that the PR stays draft until they mark it
ready (converting to ready triggers claude-review). Include the post-merge
checklist: Dagster materializes both views on the kipptaf location deploy;
Tableau data source points at
`kipptaf_tableau.rpt_tableau__student_course_grades` +
`kipptaf_tableau.rpt_tableau__gpa_cumulative_year` related on `student_number`;
exposure yml lands once the workbook LSID exists (#4340).

```

```
