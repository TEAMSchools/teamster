# GPA Quarter Target, Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every current-year high school student a target letter, a
per-course pace percent for the remaining quarters, a single quickest-win
course, a pace status, and the weighted Y1 GPA needed, surfaced on the GPA
roster sheet and the Cumulative GPA Monitor.

**Architecture:** Three new kipptaf intermediates under `models/gpa/` read
`int_powerschool__gpa_cumulative`, `base_powerschool__final_grades`, and
`int_powerschool__gradescaleitem_lookup`, all already unioned in kipptaf. Two
existing extracts gain columns, one new Tableau extract carries the course
grain, and the course extract gains `need_83`. No new sources.

**Tech Stack:** dbt 1.12 on BigQuery, kipptaf project, dbt unit tests with dict
fixtures, Trunk (sqlfluff, sqlfmt, prettier, yamllint).

**Spec:** `docs/superpowers/specs/2026-10-06-gpa-quarter-target-design.md`

Phase 2 of the spec (commitment log, leader rollup) is a separate plan. It
brings a new Google Sheet source and its own staging chain.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target`.
  Every git call is `git -C <worktree>`; every dbt call is
  `--project-dir <worktree>/src/dbt/kipptaf`. Never `cd` into it.
- dbt:
  `uv run dbt ... --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  The state path is absolute. Unit tests:
  `uv run dbt test --select <unit_test_name> --project-dir <worktree>/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
- SQL follows `.claude/rules/dbt-sql.md`: no `qualify`, no `order by`, no
  positional `group by`, no subqueries, max one level of function nesting,
  trailing commas, explicit column lists in every union branch and every `rpt_`
  final select.
- YAML follows `.claude/rules/dbt-yaml.md`: unit-test dict scalars unquoted,
  every `expect` row lists the same columns, every new model and column has a
  `description`, student-level columns carry `config.meta.contains_pii: true`.
- `rpt_` models are contract-enforced. Every added column goes in the properties
  yml with `data_type`.
- No quarter GPA anywhere. Percent per course only.
- Status values are exactly `on_pace`, `not_on_pace`, `goal_not_attainable`,
  `unknown`.
- Target letter is floored at the B cutoff (83).
- `gpa_needed_for_cumulative_3_0` is rounded to 4 decimals before any cutoff
  lookup.
- Before every push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- Commit messages end with
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

- A student with no graded course yet in September: `gpa_needed_unweighted`
  computes, target is B or higher, `pace_status` is `not_on_pace`, every course
  has a pace equal to the target cutoff. Pinned in Task 1 (student 4) and Task 2
  (student 4).
- A course whose terms have all ended with no stored Y1: it is `is_locked`,
  excluded from pace, excluded from quickest win, and still counts toward
  `n_courses_below_target` only if below target. Pinned in Task 2 (student 3)
  and Task 3.
- A course on an unresolvable grade scale: the student's `pace_status` reads
  `unknown`, not `goal_not_attainable`, and the course has no pace. Pinned in
  Task 1 (student 5).
- A student already above 3.0 with negative needed: status `on_pace`, target B,
  pace per course is the B cutoff, nothing reads negative. Pinned in Task 1
  (student 3) and Task 2.
- An exam-term course: `remaining_weight` includes the exam weights and the pace
  is higher than a quarter-only pace would be. Pinned in Task 2 (student 2,
  course C2).

---

### Task 1: `int_powerschool__student_y1_target`

**Files:**

- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/int_powerschool__student_y1_target.sql`
- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/properties/int_powerschool__student_y1_target.yml`

**Interfaces:**

- Consumes: `int_powerschool__gpa_cumulative` (kipptaf union; `studentid`,
  `schoolid`, `_dbt_source_project`, `gpa_needed_for_cumulative_3_0`,
  `is_cumulative_3_0_attainable`, `cumulative_y1_gpa_projected_unweighted`,
  `potential_gpa_credits_current_year`), `base_powerschool__final_grades`
  (`studentid`, `course_number`, `academic_year`, `_dbt_source_project`,
  `exclude_from_gpa`, `is_dropped_section`, `potential_credit_hours`,
  `courses_gradescaleid`), `int_powerschool__gradescaleitem_lookup`
  (`gradescale_name`, `letter_grade`, `grade_points`, `min_cutoffpercentage`),
  `int_extracts__student_enrollments` (`studentid`, `schoolid`, `yearid`,
  `academic_year`, `rn_year`, `school_level`, `_dbt_source_project`).
- Produces: one row per `studentid`, `schoolid`, `_dbt_source_project` with
  `gpa_needed_unweighted float64`, `target_cutoff_percent float64`,
  `target_letter_grade string`, `target_grade_points float64`,
  `schedule_bump float64`, `gpa_needed_weighted float64`, `pace_status string`,
  `is_cumulative_3_0_attainable boolean`,
  `cumulative_y1_gpa_projected_unweighted float64`. Tasks 2, 3, 5, 6 join on the
  three key columns.

- [ ] **Step 1: Write the failing unit test**

Create the properties file with the model entry and the unit test. The model
does not exist yet, so the test fails at parse.

```yaml
models:
  - name: int_powerschool__student_y1_target
    description: >-
      One row per current-year high school student and school with the
      unweighted letter target they must average across every GPA course to
      finish at a 3.0 unweighted cumulative, the weighted Y1 GPA that target
      corresponds to on their own schedule, and a pace status. The target is the
      lowest unweighted letter whose grade points reach the needed GPA, floored
      at B. Reads the needed GPA and attainability from
      `int_powerschool__gpa_cumulative`; neither is recomputed here.
    config:
      meta:
        contains_pii: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - studentid
              - schoolid
              - _dbt_source_project
    columns:
      - name: pace_status
        data_type: string
        description: >-
          `unknown` when the needed GPA or attainability is NULL;
          `goal_not_attainable` when attainability is false or no unweighted
          letter reaches the needed GPA; `on_pace` when the projected unweighted
          cumulative is at or above 3.0; `not_on_pace` otherwise.
        data_tests:
          - not_null
          - accepted_values:
              arguments:
                values:
                  - on_pace
                  - not_on_pace
                  - goal_not_attainable
                  - unknown
      - name: studentid
        data_type: int64
      - name: schoolid
        data_type: int64
      - name: _dbt_source_project
        data_type: string
      - name: student_number
        data_type: int64
        config:
          meta:
            contains_pii: true
      - name: gpa_needed_unweighted
        data_type: float64
        description: >-
          `gpa_needed_for_cumulative_3_0` rounded to 4 decimals, so a float
          artifact such as 2.6700000000000004 does not pick the wrong letter.
      - name: target_cutoff_percent
        data_type: float64
        description: >-
          Lowest unweighted cutoff whose grade points reach
          `gpa_needed_unweighted`, floored at 83. NULL when no letter reaches
          it.
      - name: target_letter_grade
        data_type: string
      - name: target_grade_points
        data_type: float64
      - name: schedule_bump
        data_type: float64
        description: >-
          Credit-weighted grade-point bonus of the student's current-year GPA
          courses — 1.0 per credit on the KIPP NJ 2019 weighted scale, 0.5 on
          the 2024 honors scale, 0 otherwise — divided by total GPA credits.
          Zero for a student with no weighted courses.
      - name: gpa_needed_weighted
        data_type: float64
        description: >-
          `gpa_needed_unweighted` plus `schedule_bump`. Comparable to the
          weighted Y1 GPA PowerSchool shows. Hitting it guarantees the
          unweighted goal, because failing a weighted course only shrinks the
          real bonus.
      - name: is_cumulative_3_0_attainable
        data_type: boolean
      - name: cumulative_y1_gpa_projected_unweighted
        data_type: float64

unit_tests:
  - name: unit_gpa_student_y1_target
    description: >-
      Student 1 needs 3.11, has one AP course of 5 credits among 20, so the
      target is B+ (3.33, 87), the bump is 0.25, weighted needed is 3.36, and
      with a projected 2.9 the status is not_on_pace. Student 2 needs 4.5 and is
      flagged unattainable: no letter reaches it, target NULL, status
      goal_not_attainable. Student 3 needs -0.5 with a projected 3.6: target
      floors at B (83, 3.0) and status is on_pace. Student 4 has no graded
      course and needs exactly 3.0: target B, status not_on_pace. Student 5 has
      a NULL attainability flag: status unknown, target still B+.
    model: int_powerschool__student_y1_target
    overrides:
      vars:
        current_academic_year: 2025
    given:
      - input: ref('int_powerschool__gpa_cumulative')
        rows:
          - {
              studentid: 1,
              schoolid: 101,
              _dbt_source_project: kippnewark,
              gpa_needed_for_cumulative_3_0: 3.11,
              is_cumulative_3_0_attainable: true,
              cumulative_y1_gpa_projected_unweighted: 2.9,
              potential_gpa_credits_current_year: 20.0,
            }
          - {
              studentid: 2,
              schoolid: 101,
              _dbt_source_project: kippnewark,
              gpa_needed_for_cumulative_3_0: 4.5,
              is_cumulative_3_0_attainable: false,
              cumulative_y1_gpa_projected_unweighted: 2.1,
              potential_gpa_credits_current_year: 20.0,
            }
          - {
              studentid: 3,
              schoolid: 101,
              _dbt_source_project: kippnewark,
              gpa_needed_for_cumulative_3_0: -0.5,
              is_cumulative_3_0_attainable: true,
              cumulative_y1_gpa_projected_unweighted: 3.6,
              potential_gpa_credits_current_year: 20.0,
            }
          - {
              studentid: 4,
              schoolid: 101,
              _dbt_source_project: kippnewark,
              gpa_needed_for_cumulative_3_0: 3.0,
              is_cumulative_3_0_attainable: true,
              cumulative_y1_gpa_projected_unweighted: null,
              potential_gpa_credits_current_year: 20.0,
            }
          - {
              studentid: 5,
              schoolid: 101,
              _dbt_source_project: kippnewark,
              gpa_needed_for_cumulative_3_0: 3.11,
              is_cumulative_3_0_attainable: null,
              cumulative_y1_gpa_projected_unweighted: 2.9,
              potential_gpa_credits_current_year: 20.0,
            }
      - input: ref('base_powerschool__final_grades')
        rows:
          - {
              studentid: 1,
              course_number: C1,
              academic_year: 2025,
              _dbt_source_project: kippnewark,
              exclude_from_gpa: 0,
              is_dropped_section: false,
              potential_credit_hours: 5.0,
              courses_gradescaleid: 991,
            }
          - {
              studentid: 1,
              course_number: C2,
              academic_year: 2025,
              _dbt_source_project: kippnewark,
              exclude_from_gpa: 0,
              is_dropped_section: false,
              potential_credit_hours: 15.0,
              courses_gradescaleid: 976,
            }
          - {
              studentid: 2,
              course_number: C2,
              academic_year: 2025,
              _dbt_source_project: kippnewark,
              exclude_from_gpa: 0,
              is_dropped_section: false,
              potential_credit_hours: 20.0,
              courses_gradescaleid: 976,
            }
          - {
              studentid: 3,
              course_number: C2,
              academic_year: 2025,
              _dbt_source_project: kippnewark,
              exclude_from_gpa: 0,
              is_dropped_section: false,
              potential_credit_hours: 20.0,
              courses_gradescaleid: 976,
            }
          - {
              studentid: 4,
              course_number: C2,
              academic_year: 2025,
              _dbt_source_project: kippnewark,
              exclude_from_gpa: 0,
              is_dropped_section: false,
              potential_credit_hours: 20.0,
              courses_gradescaleid: 976,
            }
          - {
              studentid: 5,
              course_number: C2,
              academic_year: 2025,
              _dbt_source_project: kippnewark,
              exclude_from_gpa: 0,
              is_dropped_section: false,
              potential_credit_hours: 20.0,
              courses_gradescaleid: 976,
            }
      - input: ref('int_powerschool__gradescaleitem_lookup')
        rows:
          - {
              gradescale_name: KIPP NJ 2019 (5-12) Unweighted,
              letter_grade: A,
              grade_points: 4.0,
              min_cutoffpercentage: 93,
            }
          - {
              gradescale_name: KIPP NJ 2019 (5-12) Unweighted,
              letter_grade: A-,
              grade_points: 3.67,
              min_cutoffpercentage: 90,
            }
          - {
              gradescale_name: KIPP NJ 2019 (5-12) Unweighted,
              letter_grade: B+,
              grade_points: 3.33,
              min_cutoffpercentage: 87,
            }
          - {
              gradescale_name: KIPP NJ 2019 (5-12) Unweighted,
              letter_grade: B,
              grade_points: 3.0,
              min_cutoffpercentage: 83,
            }
          - {
              gradescale_name: KIPP NJ 2019 (5-12) Unweighted,
              letter_grade: B-,
              grade_points: 2.67,
              min_cutoffpercentage: 80,
            }
          - {
              gradescale_name: KIPP NJ 2019 (5-12) Unweighted,
              letter_grade: F,
              grade_points: 0.0,
              min_cutoffpercentage: 0,
            }
      - input: ref('int_extracts__student_enrollments')
        rows:
          - {
              studentid: 1,
              schoolid: 101,
              yearid: 35,
              academic_year: 2025,
              rn_year: 1,
              school_level: HS,
              student_number: 1001,
              _dbt_source_project: kippnewark,
            }
          - {
              studentid: 2,
              schoolid: 101,
              yearid: 35,
              academic_year: 2025,
              rn_year: 1,
              school_level: HS,
              student_number: 1002,
              _dbt_source_project: kippnewark,
            }
          - {
              studentid: 3,
              schoolid: 101,
              yearid: 35,
              academic_year: 2025,
              rn_year: 1,
              school_level: HS,
              student_number: 1003,
              _dbt_source_project: kippnewark,
            }
          - {
              studentid: 4,
              schoolid: 101,
              yearid: 35,
              academic_year: 2025,
              rn_year: 1,
              school_level: HS,
              student_number: 1004,
              _dbt_source_project: kippnewark,
            }
          - {
              studentid: 5,
              schoolid: 101,
              yearid: 35,
              academic_year: 2025,
              rn_year: 1,
              school_level: HS,
              student_number: 1005,
              _dbt_source_project: kippnewark,
            }
    expect:
      rows:
        - {
            studentid: 1,
            gpa_needed_unweighted: 3.11,
            target_cutoff_percent: 87.0,
            target_letter_grade: B+,
            schedule_bump: 0.25,
            gpa_needed_weighted: 3.36,
            pace_status: not_on_pace,
          }
        - {
            studentid: 2,
            gpa_needed_unweighted: 4.5,
            target_cutoff_percent: null,
            target_letter_grade: null,
            schedule_bump: 0.0,
            gpa_needed_weighted: 4.5,
            pace_status: goal_not_attainable,
          }
        - {
            studentid: 3,
            gpa_needed_unweighted: -0.5,
            target_cutoff_percent: 83.0,
            target_letter_grade: B,
            schedule_bump: 0.0,
            gpa_needed_weighted: -0.5,
            pace_status: on_pace,
          }
        - {
            studentid: 4,
            gpa_needed_unweighted: 3.0,
            target_cutoff_percent: 83.0,
            target_letter_grade: B,
            schedule_bump: 0.0,
            gpa_needed_weighted: 3.0,
            pace_status: not_on_pace,
          }
        - {
            studentid: 5,
            gpa_needed_unweighted: 3.11,
            target_cutoff_percent: 87.0,
            target_letter_grade: B+,
            schedule_bump: 0.0,
            gpa_needed_weighted: 3.11,
            pace_status: unknown,
          }
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run dbt test --select unit_gpa_student_y1_target --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 20
```

Expected: a parse error naming `int_powerschool__student_y1_target` as a model
that does not exist.

- [ ] **Step 3: Write the model**

```sql
with
    unweighted_scale as (
        select letter_grade, grade_points, min_cutoffpercentage,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        /* every scale in use shares these cutoffs; 2019 Unweighted is the
           reference */
        where
            gradescale_name = 'KIPP NJ 2019 (5-12) Unweighted'
            and min_cutoffpercentage >= 83
    ),

    schedule as (
        select
            studentid,
            _dbt_source_project,

            sum(potential_credit_hours) as gpa_credits,
            sum(
                potential_credit_hours
                * case courses_gradescaleid when 991 then 1.0 when 1075 then 0.5 else 0.0 end
            ) as bump_points,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and exclude_from_gpa = 0
            and not is_dropped_section
            and potential_credit_hours > 0
        group by studentid, _dbt_source_project
    ),

    students as (
        select
            co.studentid,
            co.schoolid,
            co.student_number,
            co._dbt_source_project,

            gc.is_cumulative_3_0_attainable,
            gc.cumulative_y1_gpa_projected_unweighted,

            round(gc.gpa_needed_for_cumulative_3_0, 4) as gpa_needed_unweighted,
            safe_divide(s.bump_points, s.gpa_credits) as schedule_bump,
        from {{ ref("int_extracts__student_enrollments") }} as co
        inner join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on co.studentid = gc.studentid
            and co.schoolid = gc.schoolid
            and co._dbt_source_project = gc._dbt_source_project
        left join
            schedule as s
            on co.studentid = s.studentid
            and co._dbt_source_project = s._dbt_source_project
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and co.school_level = 'HS'
    ),

    targets as (
        select
            st.studentid,
            st.schoolid,
            st._dbt_source_project,

            min(us.min_cutoffpercentage) as target_cutoff_percent,
        from students as st
        inner join unweighted_scale as us on st.gpa_needed_unweighted <= us.grade_points
        group by st.studentid, st.schoolid, st._dbt_source_project
    ),

    with_target as (
        select
            st.studentid,
            st.schoolid,
            st.student_number,
            st._dbt_source_project,
            st.gpa_needed_unweighted,
            st.schedule_bump,
            st.is_cumulative_3_0_attainable,
            st.cumulative_y1_gpa_projected_unweighted,

            t.target_cutoff_percent,

            us.letter_grade as target_letter_grade,
            us.grade_points as target_grade_points,

            coalesce(st.schedule_bump, 0.0) as schedule_bump_filled,
        from students as st
        left join
            targets as t
            on st.studentid = t.studentid
            and st.schoolid = t.schoolid
            and st._dbt_source_project = t._dbt_source_project
        left join unweighted_scale as us on t.target_cutoff_percent = us.min_cutoffpercentage
    )

select
    studentid,
    schoolid,
    student_number,
    _dbt_source_project,
    gpa_needed_unweighted,
    target_cutoff_percent,
    target_letter_grade,
    target_grade_points,
    is_cumulative_3_0_attainable,
    cumulative_y1_gpa_projected_unweighted,

    schedule_bump_filled as schedule_bump,

    round(gpa_needed_unweighted + schedule_bump_filled, 2) as gpa_needed_weighted,

    case
        when gpa_needed_unweighted is null or is_cumulative_3_0_attainable is null
        then 'unknown'
        when not is_cumulative_3_0_attainable or target_cutoff_percent is null
        then 'goal_not_attainable'
        when cumulative_y1_gpa_projected_unweighted >= 3.0
        then 'on_pace'
        else 'not_on_pace'
    end as pace_status,
from with_target
```

The `targets` join is a one-sided comparison on purpose: it is the lookup
itself, not a calculation. The `where min_cutoffpercentage >= 83` in
`unweighted_scale` is the B floor. `schedule_bump` is exposed as the coalesced
value so a student with no weighted courses reads 0, not NULL.

- [ ] **Step 4: Run the test to verify it passes**

Same command as Step 2. Expected: `PASS=1`.

If student 1's `gpa_needed_weighted` reads 3.36 but `schedule_bump` reads
0.25000000000000006, round `schedule_bump_filled` to 4 decimals in the final
select and adjust nothing else.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/gpa/intermediate/int_powerschool__student_y1_target.sql src/dbt/kipptaf/models/gpa/intermediate/properties/int_powerschool__student_y1_target.yml </dev/null
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target add src/dbt/kipptaf/models/gpa/intermediate/int_powerschool__student_y1_target.sql src/dbt/kipptaf/models/gpa/intermediate/properties/int_powerschool__student_y1_target.yml
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target commit -m "feat(dbt): add int_powerschool__student_y1_target

Refs #5768

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `int_powerschool__course_pace`

**Files:**

- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/int_powerschool__course_pace.sql`
- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/properties/int_powerschool__course_pace.yml`

**Interfaces:**

- Consumes: Task 1's `int_powerschool__student_y1_target` (`studentid`,
  `schoolid`, `_dbt_source_project`, `target_cutoff_percent`);
  `base_powerschool__final_grades` (`studentid`, `course_number`, `course_name`,
  `academic_year`, `_dbt_source_project`, `storecode`, `exclude_from_gpa`,
  `is_dropped_section`, `potential_credit_hours`,
  `courses_gradescaleid_unweighted`, `termbin_start_date`, `termbin_end_date`,
  `termbin_is_current`, `term_weighted_points_possible`,
  `term_percent_grade_adjusted`, `y1_percent_grade_adjusted`,
  `y1_grade_points_unweighted`).
- Produces: one row per `studentid`, `course_number`, `_dbt_source_project` for
  current-year GPA courses, with `schoolid int64`, `course_name string`,
  `potential_credit_hours float64`, `courses_gradescaleid_unweighted int64`,
  `target_cutoff_percent float64`, `y1_percent_current float64`,
  `y1_grade_points_unweighted_current float64`, `term_percent_current float64`,
  `total_weight float64`, `points_banked float64`, `remaining_weight float64`,
  `pace_percent float64`, `is_below_target boolean`, `is_secured boolean`,
  `is_locked boolean`. Task 3 reads every column; Tasks 5 and 7 read the pace
  and flags.

- [ ] **Step 1: Write the failing unit test**

```yaml
models:
  - name: int_powerschool__course_pace
    description: >-
      One row per current-year GPA course per student with the average percent
      the student needs in each remaining term for the course Y1 to land on
      their target cutoff from `int_powerschool__student_y1_target`. A term counts
      as remaining until its termbin ends, so the in-progress term is in the
      remaining weight and the pace does not swing with each posted
      assignment. Exam terms are remaining terms too. A course whose every
      term has ended is locked; it has no pace and stays in the GPA.
    config:
      meta:
        contains_pii: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - studentid
              - course_number
              - _dbt_source_project
    columns:
      - name: pace_percent
        data_type: float64
        description: >-
          (target cutoff × total weight − points banked) / remaining weight, in
          percent. NULL when the course is locked or has no target.
        data_tests:
          - dbt_utils.accepted_range:
              arguments:
                min_value: 0
                max_value: 200
                inclusive: true
              config:
                where: pace_percent is not null
      - name: studentid
        data_type: int64
      - name: schoolid
        data_type: int64
      - name: course_number
        data_type: string
      - name: course_name
        data_type: string
      - name: _dbt_source_project
        data_type: string
      - name: potential_credit_hours
        data_type: float64
      - name: courses_gradescaleid_unweighted
        data_type: int64
      - name: target_cutoff_percent
        data_type: float64
      - name: y1_percent_current
        data_type: float64
        description: Live Y1 percent on the current termbin row, else the latest started term's.
      - name: y1_grade_points_unweighted_current
        data_type: float64
      - name: term_percent_current
        data_type: float64
        description: Percent in the in-progress term; NULL before any grade posts.
      - name: total_weight
        data_type: float64
        description: Sum of term weights for the course, 100 for four 25-point quarters, 98 with two 5-point exams.
      - name: points_banked
        data_type: float64
        description: Sum of percent × weight over terms whose termbin has ended.
      - name: remaining_weight
        data_type: float64
      - name: is_below_target
        data_type: boolean
        description: `y1_percent_current` is below `target_cutoff_percent`.
      - name: is_secured
        data_type: boolean
        description: Pace at or below 50, the live-gradebook floor, so the target is already met.
      - name: is_locked
        data_type: boolean
        description: Every termbin for the course has ended.

unit_tests:
  - name: unit_gpa_course_pace
    description: >-
      Target cutoff 87 for every student. Student 1 course C1 has four
      25-point quarters, Q1 ended at 80, Q2 in progress at 85: banked 2000,
      remaining 75, pace (8700 − 2000) / 75 = 89.33, below target (Y1 82).
      Student 2 course C2 has four 22-point quarters and two 5-point exams, Q1
      ended at 80: banked 1760, remaining 76, pace (8526 − 1760) / 76 = 89.03,
      higher than the 87 a quarter-only pace would give because the exam
      weights are remaining too.
      Student 3 course C3 has two terms that both ended: locked, pace NULL.
      Student 4 course C4 has no grade yet and nothing ended: banked 0,
      remaining 100, pace 87, not below target because Y1 is NULL. Student 5
      course C5 has Y1 95 with Q1 at 95 ended: pace (8700 − 2375) / 75 = 84.33
      and not below target.
    model: int_powerschool__course_pace
    overrides:
      vars:
        current_academic_year: 2025
    given:
      - input: ref('int_powerschool__student_y1_target')
        rows:
          - { studentid: 1, schoolid: 101, _dbt_source_project: kippnewark, target_cutoff_percent: 87.0 }
          - { studentid: 2, schoolid: 101, _dbt_source_project: kippnewark, target_cutoff_percent: 87.0 }
          - { studentid: 3, schoolid: 101, _dbt_source_project: kippnewark, target_cutoff_percent: 87.0 }
          - { studentid: 4, schoolid: 101, _dbt_source_project: kippnewark, target_cutoff_percent: 87.0 }
          - { studentid: 5, schoolid: 101, _dbt_source_project: kippnewark, target_cutoff_percent: 87.0 }
      - input: ref('base_powerschool__final_grades')
        rows:
          - { studentid: 1, course_number: C1, course_name: English, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q1, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 2000-01-01, termbin_end_date: 2000-03-31, termbin_is_current: false, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: 80.0, y1_percent_grade_adjusted: 80.0, y1_grade_points_unweighted: 2.67 }
          - { studentid: 1, course_number: C1, course_name: English, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q2, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 2000-04-01, termbin_end_date: 9999-06-30, termbin_is_current: true, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: 85.0, y1_percent_grade_adjusted: 82.0, y1_grade_points_unweighted: 2.67 }
          - { studentid: 1, course_number: C1, course_name: English, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q3, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-07-01, termbin_end_date: 9999-09-30, termbin_is_current: false, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 1, course_number: C1, course_name: English, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q4, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-10-01, termbin_end_date: 9999-12-31, termbin_is_current: false, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 2, course_number: C2, course_name: Biology, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q1, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 2000-01-01, termbin_end_date: 2000-03-31, termbin_is_current: false, term_weighted_points_possible: 22.0, term_percent_grade_adjusted: 80.0, y1_percent_grade_adjusted: 80.0, y1_grade_points_unweighted: 2.67 }
          - { studentid: 2, course_number: C2, course_name: Biology, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q2, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 2000-04-01, termbin_end_date: 9999-06-30, termbin_is_current: true, term_weighted_points_possible: 22.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: 80.0, y1_grade_points_unweighted: 2.67 }
          - { studentid: 2, course_number: C2, course_name: Biology, academic_year: 2025, _dbt_source_project: kippnewark, storecode: E1, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-06-01, termbin_end_date: 9999-06-30, termbin_is_current: false, term_weighted_points_possible: 5.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 2, course_number: C2, course_name: Biology, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q3, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-07-01, termbin_end_date: 9999-09-30, termbin_is_current: false, term_weighted_points_possible: 22.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 2, course_number: C2, course_name: Biology, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q4, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-10-01, termbin_end_date: 9999-12-31, termbin_is_current: false, term_weighted_points_possible: 22.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 2, course_number: C2, course_name: Biology, academic_year: 2025, _dbt_source_project: kippnewark, storecode: E2, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-12-01, termbin_end_date: 9999-12-31, termbin_is_current: false, term_weighted_points_possible: 5.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 3, course_number: C3, course_name: Health, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q1, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 2.5, courses_gradescaleid_unweighted: 976, termbin_start_date: 2000-01-01, termbin_end_date: 2000-03-31, termbin_is_current: false, term_weighted_points_possible: 50.0, term_percent_grade_adjusted: 70.0, y1_percent_grade_adjusted: 70.0, y1_grade_points_unweighted: 1.67 }
          - { studentid: 3, course_number: C3, course_name: Health, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q2, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 2.5, courses_gradescaleid_unweighted: 976, termbin_start_date: 2000-04-01, termbin_end_date: 2000-06-30, termbin_is_current: false, term_weighted_points_possible: 50.0, term_percent_grade_adjusted: 74.0, y1_percent_grade_adjusted: 72.0, y1_grade_points_unweighted: 1.67 }
          - { studentid: 4, course_number: C4, course_name: Algebra, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q1, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 2000-01-01, termbin_end_date: 9999-03-31, termbin_is_current: true, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 4, course_number: C4, course_name: Algebra, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q2, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-04-01, termbin_end_date: 9999-06-30, termbin_is_current: false, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 4, course_number: C4, course_name: Algebra, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q3, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-07-01, termbin_end_date: 9999-09-30, termbin_is_current: false, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 4, course_number: C4, course_name: Algebra, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q4, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-10-01, termbin_end_date: 9999-12-31, termbin_is_current: false, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 5, course_number: C5, course_name: History, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q1, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 2000-01-01, termbin_end_date: 2000-03-31, termbin_is_current: false, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: 95.0, y1_percent_grade_adjusted: 95.0, y1_grade_points_unweighted: 4.0 }
          - { studentid: 5, course_number: C5, course_name: History, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q2, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 2000-04-01, termbin_end_date: 9999-06-30, termbin_is_current: true, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: 95.0, y1_grade_points_unweighted: 4.0 }
          - { studentid: 5, course_number: C5, course_name: History, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q3, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-07-01, termbin_end_date: 9999-09-30, termbin_is_current: false, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
          - { studentid: 5, course_number: C5, course_name: History, academic_year: 2025, _dbt_source_project: kippnewark, storecode: Q4, exclude_from_gpa: 0, is_dropped_section: false, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, termbin_start_date: 9999-10-01, termbin_end_date: 9999-12-31, termbin_is_current: false, term_weighted_points_possible: 25.0, term_percent_grade_adjusted: null, y1_percent_grade_adjusted: null, y1_grade_points_unweighted: null }
    expect:
      rows:
        - { studentid: 1, course_number: C1, total_weight: 100.0, points_banked: 2000.0, remaining_weight: 75.0, pace_percent: 89.33, is_below_target: true, is_secured: false, is_locked: false }
        - { studentid: 2, course_number: C2, total_weight: 98.0, points_banked: 1760.0, remaining_weight: 76.0, pace_percent: 89.03, is_below_target: true, is_secured: false, is_locked: false }
        - { studentid: 3, course_number: C3, total_weight: 100.0, points_banked: 7200.0, remaining_weight: 0.0, pace_percent: null, is_below_target: true, is_secured: false, is_locked: true }
        - { studentid: 4, course_number: C4, total_weight: 100.0, points_banked: 0.0, remaining_weight: 100.0, pace_percent: 87.0, is_below_target: false, is_secured: false, is_locked: false }
        - { studentid: 5, course_number: C5, total_weight: 100.0, points_banked: 2375.0, remaining_weight: 75.0, pace_percent: 84.33, is_below_target: false, is_secured: false, is_locked: false }
```

A `termbin_end_date` in year 2000 has ended; one in 9999 has not. The
`current_date` comparison in the model makes those fixtures stable.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run dbt test --select unit_gpa_course_pace --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 20
```

Expected: parse error, model not found.

- [ ] **Step 3: Write the model**

```sql
with
    term_rows as (
        select
            studentid,
            course_number,
            course_name,
            academic_year,
            _dbt_source_project,
            potential_credit_hours,
            courses_gradescaleid_unweighted,
            termbin_start_date,
            termbin_end_date,
            termbin_is_current,
            term_weighted_points_possible,
            term_percent_grade_adjusted,
            y1_percent_grade_adjusted,
            y1_grade_points_unweighted,

            termbin_end_date < current_date('{{ var("local_timezone") }}') as is_ended,
            termbin_start_date
            <= current_date('{{ var("local_timezone") }}') as is_started,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and exclude_from_gpa = 0
            and not is_dropped_section
            and potential_credit_hours > 0
    ),

    term_rows_ranked as (
        select
            *,

            row_number() over (
                partition by studentid, course_number, _dbt_source_project
                order by termbin_is_current desc, is_started desc, termbin_end_date desc
            ) as rn_current,
        from term_rows
    ),

    courses as (
        select
            studentid,
            course_number,
            _dbt_source_project,

            max(course_name) as course_name,
            max(potential_credit_hours) as potential_credit_hours,
            max(courses_gradescaleid_unweighted) as courses_gradescaleid_unweighted,
            sum(term_weighted_points_possible) as total_weight,
            sum(
                if(is_ended, term_percent_grade_adjusted * term_weighted_points_possible, 0.0)
            ) as points_banked,
            sum(if(is_ended, 0.0, term_weighted_points_possible)) as remaining_weight,
            logical_and(is_ended) as is_locked,
        from term_rows
        group by studentid, course_number, _dbt_source_project
    ),

    current_values as (
        select
            studentid,
            course_number,
            _dbt_source_project,
            y1_percent_grade_adjusted as y1_percent_current,
            y1_grade_points_unweighted as y1_grade_points_unweighted_current,

            if(termbin_is_current, term_percent_grade_adjusted, null) as term_percent_current,
        from term_rows_ranked
        where rn_current = 1
    ),

    paced as (
        select
            c.studentid,
            c.course_number,
            c.course_name,
            c._dbt_source_project,
            c.potential_credit_hours,
            c.courses_gradescaleid_unweighted,
            c.total_weight,
            c.points_banked,
            c.remaining_weight,
            c.is_locked,

            cv.y1_percent_current,
            cv.y1_grade_points_unweighted_current,
            cv.term_percent_current,

            t.schoolid,
            t.target_cutoff_percent,

            round(
                safe_divide(
                    t.target_cutoff_percent * c.total_weight - c.points_banked,
                    c.remaining_weight
                ),
                2
            ) as pace_percent,
        from courses as c
        inner join
            current_values as cv
            on c.studentid = cv.studentid
            and c.course_number = cv.course_number
            and c._dbt_source_project = cv._dbt_source_project
        inner join
            {{ ref("int_powerschool__student_y1_target") }} as t
            on c.studentid = t.studentid
            and c._dbt_source_project = t._dbt_source_project
    )

select
    studentid,
    schoolid,
    course_number,
    course_name,
    _dbt_source_project,
    potential_credit_hours,
    courses_gradescaleid_unweighted,
    target_cutoff_percent,
    y1_percent_current,
    y1_grade_points_unweighted_current,
    term_percent_current,
    total_weight,
    points_banked,
    remaining_weight,
    is_locked,

    if(is_locked, null, pace_percent) as pace_percent,

    coalesce(y1_percent_current < target_cutoff_percent, false) as is_below_target,
    coalesce(not is_locked and pace_percent <= 50, false) as is_secured,
from paced
```

`sum(if(is_ended, 0.0, weight))` is 0 for a locked course, and `safe_divide`
returns NULL on it, so the final `if(is_locked, ...)` is belt and braces. The
ranked CTE is the repo's window-then-filter idiom; `qualify` is banned.

- [ ] **Step 4: Run the test to verify it passes**

Same command as Step 2. Expected: `PASS=1`.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/gpa/intermediate/int_powerschool__course_pace.sql src/dbt/kipptaf/models/gpa/intermediate/properties/int_powerschool__course_pace.yml </dev/null
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target add src/dbt/kipptaf/models/gpa/intermediate/int_powerschool__course_pace.sql src/dbt/kipptaf/models/gpa/intermediate/properties/int_powerschool__course_pace.yml
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target commit -m "feat(dbt): add int_powerschool__course_pace

Refs #5768

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `int_gpa__course_quickest_win`

**Files:**

- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/int_gpa__course_quickest_win.sql`
- Create:
  `src/dbt/kipptaf/models/gpa/intermediate/properties/int_gpa__course_quickest_win.yml`

**Interfaces:**

- Consumes: Task 2's `int_powerschool__course_pace` (every column);
  `int_powerschool__gradescaleitem_lookup` (`gradescale_name`, `letter_grade`,
  `grade_points`, `min_cutoffpercentage`).
- Produces: one row per `studentid`, `course_number`, `_dbt_source_project` with
  `schoolid int64`, `course_name string`, `next_letter_grade string`,
  `next_cutoff_percent float64`, `next_grade_points float64`,
  `points_gained float64`, `pace_percent_to_next float64`, `need_gap float64`,
  `score float64`, `quickest_win_rank int64`. Rank is NULL for courses that do
  not qualify. Tasks 5 and 7 read rank 1.

- [ ] **Step 1: Write the failing unit test**

```yaml
models:
  - name: int_gpa__course_quickest_win
    description: >-
      Ranks each student's unlocked GPA courses by how cheaply a letter-grade
      step can be bought this year: unweighted grade points gained at the next
      letter times credit hours, divided by the percent-point gap between the
      pace to that letter and the student's current term percent, floored at
      one point. Courses below the student's target rank first. A course has
      no rank when it is locked, when its next letter needs more than 100
      percent, or when the gap is zero or negative. Derived from full-year
      term weights, not the current-term `need_next`, which over-ranks
      second-semester courses.
    config:
      meta:
        contains_pii: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - studentid
              - course_number
              - _dbt_source_project
    columns:
      - name: quickest_win_rank
        data_type: int64
        description: 1 is the quickest win. NULL when the course does not qualify.
        data_tests:
          - dbt_utils.accepted_range:
              arguments:
                min_value: 1
                inclusive: true
              config:
                where: quickest_win_rank is not null
      - name: studentid
        data_type: int64
      - name: schoolid
        data_type: int64
      - name: course_number
        data_type: string
      - name: course_name
        data_type: string
      - name: _dbt_source_project
        data_type: string
      - name: next_letter_grade
        data_type: string
        description: Lowest unweighted letter with strictly more grade points than the course's current unweighted Y1 points.
      - name: next_cutoff_percent
        data_type: float64
      - name: next_grade_points
        data_type: float64
      - name: points_gained
        data_type: float64
      - name: pace_percent_to_next
        data_type: float64
        description: The pace formula with the next cutoff as target.
      - name: need_gap
        data_type: float64
        description: `pace_percent_to_next` minus the current term percent (or the Y1 percent before any term grade posts), floored at 1.
      - name: score
        data_type: float64

unit_tests:
  - name: unit_gpa_course_quickest_win
    description: >-
      Student 1 has three courses, all 100 total weight, 2000 banked, 75
      remaining. C1 is at Y1 82 / B- (2.67), term 85, below target: next is B
      at 83, pace (8300 − 2000) / 75 = 84, gap max(84 − 85, 1) = 1, score 5 ×
      0.33 / 1 = 1.65, rank 1. C2 is at Y1 88 / B+ (3.33), term 88, not below
      target 87: next A- at 90, pace (9000 − 2000) / 75 = 93.33, gap 5.33,
      score 5 × 0.34 / 5.33 = 0.32, rank 2. C3 is locked: no rank. C4 is at F
      (0.0) with term 40: next is B- at 80 (the scale fixture has no D or C
      rows), pace (8000 − 2000) / 75 = 80, gap 40, score 5 × 2.67 / 40 = 0.33,
      below target so it outranks C2: rank 2, and C2 becomes rank 3.
    model: int_gpa__course_quickest_win
    overrides:
      vars:
        current_academic_year: 2025
    given:
      - input: ref('int_powerschool__course_pace')
        rows:
          - { studentid: 1, schoolid: 101, course_number: C1, course_name: English, _dbt_source_project: kippnewark, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, target_cutoff_percent: 87.0, y1_percent_current: 82.0, y1_grade_points_unweighted_current: 2.67, term_percent_current: 85.0, total_weight: 100.0, points_banked: 2000.0, remaining_weight: 75.0, pace_percent: 89.33, is_below_target: true, is_secured: false, is_locked: false }
          - { studentid: 1, schoolid: 101, course_number: C2, course_name: Biology, _dbt_source_project: kippnewark, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, target_cutoff_percent: 87.0, y1_percent_current: 88.0, y1_grade_points_unweighted_current: 3.33, term_percent_current: 88.0, total_weight: 100.0, points_banked: 2000.0, remaining_weight: 75.0, pace_percent: 89.33, is_below_target: false, is_secured: false, is_locked: false }
          - { studentid: 1, schoolid: 101, course_number: C3, course_name: Health, _dbt_source_project: kippnewark, potential_credit_hours: 2.5, courses_gradescaleid_unweighted: 976, target_cutoff_percent: 87.0, y1_percent_current: 72.0, y1_grade_points_unweighted_current: 1.67, term_percent_current: null, total_weight: 100.0, points_banked: 7200.0, remaining_weight: 0.0, pace_percent: null, is_below_target: true, is_secured: false, is_locked: true }
          - { studentid: 1, schoolid: 101, course_number: C4, course_name: Algebra, _dbt_source_project: kippnewark, potential_credit_hours: 5.0, courses_gradescaleid_unweighted: 976, target_cutoff_percent: 87.0, y1_percent_current: 45.0, y1_grade_points_unweighted_current: 0.0, term_percent_current: 40.0, total_weight: 100.0, points_banked: 2000.0, remaining_weight: 75.0, pace_percent: 89.33, is_below_target: true, is_secured: false, is_locked: false }
      - input: ref('int_powerschool__gradescaleitem_lookup')
        rows:
          - { gradescale_name: KIPP NJ 2019 (5-12) Unweighted, letter_grade: A, grade_points: 4.0, min_cutoffpercentage: 93 }
          - { gradescale_name: KIPP NJ 2019 (5-12) Unweighted, letter_grade: A-, grade_points: 3.67, min_cutoffpercentage: 90 }
          - { gradescale_name: KIPP NJ 2019 (5-12) Unweighted, letter_grade: B+, grade_points: 3.33, min_cutoffpercentage: 87 }
          - { gradescale_name: KIPP NJ 2019 (5-12) Unweighted, letter_grade: B, grade_points: 3.0, min_cutoffpercentage: 83 }
          - { gradescale_name: KIPP NJ 2019 (5-12) Unweighted, letter_grade: B-, grade_points: 2.67, min_cutoffpercentage: 80 }
          - { gradescale_name: KIPP NJ 2019 (5-12) Unweighted, letter_grade: F, grade_points: 0.0, min_cutoffpercentage: 0 }
    expect:
      rows:
        - { studentid: 1, course_number: C1, next_letter_grade: B, next_cutoff_percent: 83.0, points_gained: 0.33, pace_percent_to_next: 84.0, need_gap: 1.0, score: 1.65, quickest_win_rank: 1 }
        - { studentid: 1, course_number: C2, next_letter_grade: A-, next_cutoff_percent: 90.0, points_gained: 0.34, pace_percent_to_next: 93.33, need_gap: 5.33, score: 0.32, quickest_win_rank: 3 }
        - { studentid: 1, course_number: C3, next_letter_grade: null, next_cutoff_percent: null, points_gained: null, pace_percent_to_next: null, need_gap: null, score: null, quickest_win_rank: null }
        - { studentid: 1, course_number: C4, next_letter_grade: B-, next_cutoff_percent: 80.0, points_gained: 2.67, pace_percent_to_next: 80.0, need_gap: 40.0, score: 0.33, quickest_win_rank: 2 }
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run dbt test --select unit_gpa_course_quickest_win --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 20
```

Expected: parse error, model not found.

- [ ] **Step 3: Write the model**

```sql
with
    unweighted_scale as (
        select letter_grade, grade_points, min_cutoffpercentage,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        where gradescale_name = 'KIPP NJ 2019 (5-12) Unweighted'
    ),

    next_rung as (
        select
            p.studentid,
            p.course_number,
            p._dbt_source_project,

            min(us.min_cutoffpercentage) as next_cutoff_percent,
        from {{ ref("int_powerschool__course_pace") }} as p
        inner join
            unweighted_scale as us
            on p.y1_grade_points_unweighted_current < us.grade_points
        where not p.is_locked
        group by p.studentid, p.course_number, p._dbt_source_project
    ),

    scored as (
        select
            p.studentid,
            p.schoolid,
            p.course_number,
            p.course_name,
            p._dbt_source_project,
            p.is_below_target,
            p.is_locked,

            nr.next_cutoff_percent,

            us.letter_grade as next_letter_grade,
            us.grade_points as next_grade_points,

            round(us.grade_points - p.y1_grade_points_unweighted_current, 2) as points_gained,
            round(
                safe_divide(
                    nr.next_cutoff_percent * p.total_weight - p.points_banked,
                    p.remaining_weight
                ),
                2
            ) as pace_percent_to_next,

            coalesce(p.term_percent_current, p.y1_percent_current) as percent_now,
            p.potential_credit_hours as credit_hours,
        from {{ ref("int_powerschool__course_pace") }} as p
        left join
            next_rung as nr
            on p.studentid = nr.studentid
            and p.course_number = nr.course_number
            and p._dbt_source_project = nr._dbt_source_project
        left join unweighted_scale as us on nr.next_cutoff_percent = us.min_cutoffpercentage
    ),

    gapped as (
        select
            *,

            greatest(pace_percent_to_next - percent_now, 1.0) as need_gap,
        from scored
    ),

    with_score as (
        select
            studentid,
            schoolid,
            course_number,
            course_name,
            _dbt_source_project,
            is_below_target,
            next_letter_grade,
            next_cutoff_percent,
            next_grade_points,
            points_gained,
            pace_percent_to_next,

            if(
                is_locked
                or next_cutoff_percent is null
                or pace_percent_to_next > 100
                or pace_percent_to_next - percent_now <= 0
                or points_gained <= 0,
                null,
                need_gap
            ) as need_gap,
            if(
                is_locked
                or next_cutoff_percent is null
                or pace_percent_to_next > 100
                or pace_percent_to_next - percent_now <= 0
                or points_gained <= 0,
                null,
                round(credit_hours * points_gained / need_gap, 2)
            ) as score,
        from gapped
    ),

    ranked as (
        select
            *,

            row_number() over (
                partition by studentid, _dbt_source_project
                order by score is null, is_below_target desc, score desc
            ) as rn,
        from with_score
    )

select
    studentid,
    schoolid,
    course_number,
    course_name,
    _dbt_source_project,
    next_letter_grade,
    next_cutoff_percent,
    next_grade_points,
    points_gained,
    pace_percent_to_next,
    need_gap,
    score,

    if(score is null, null, rn) as quickest_win_rank,
from ranked
```

The disqualifying condition is repeated in two `if` calls rather than named once
because a lateral alias would fail in BigQuery. The `order by score is null`
term pushes unqualified rows to the bottom so qualifying ranks are dense from 1.

- [ ] **Step 4: Run the test to verify it passes**

Same command as Step 2. Expected: `PASS=1`. If C1's `need_gap` reads 1.0 but
`score` reads 1.65000001, the `round(..., 2)` is on the wrong side of the
division; keep it as written above, outside the division.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/gpa/intermediate/int_gpa__course_quickest_win.sql src/dbt/kipptaf/models/gpa/intermediate/properties/int_gpa__course_quickest_win.yml </dev/null
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target add src/dbt/kipptaf/models/gpa/intermediate/int_gpa__course_quickest_win.sql src/dbt/kipptaf/models/gpa/intermediate/properties/int_gpa__course_quickest_win.yml
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target commit -m "feat(dbt): add int_gpa__course_quickest_win

Refs #5768

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `need_83` on the course extract

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`
  (the final select, near `g.need_80`)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml`

**Interfaces:**

- Consumes: `need_60`, `need_70` already on the model.
- Produces: `need_83 float64`, the percent needed in the current term for the
  course Y1 to reach 83.

- [ ] **Step 1: Add the column to the select**

Find the line `g.need_80,` in the final select and add directly after the block
of plain `g.` columns, in the simple-functions position:

```sql
    g.need_60 + (83 - 60) / 10 * (g.need_70 - g.need_60) as need_83,
```

Place it next to the existing `need_next` derivation at the bottom of the
select, which uses the same identity.

- [ ] **Step 2: Add the contract column**

In the properties yml, next to `need_80`:

```yaml
- name: need_83
  data_type: float64
  description: >-
    Percent needed in the current term for the course's year-to-date grade to
    reach 83, the B cutoff. Derived from `need_60` and `need_70` by the affine
    identity the model documents at `need_next`.
```

- [ ] **Step 3: Build the model and verify the identity**

Run:

```bash
uv run dbt build --select rpt_tableau__student_course_grades --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 15
```

Expected: the model builds (it is a view, so the contract is checked) and
existing tests pass or warn as they do on main.

Then, through the BigQuery MCP (aggregates only):

```sql
select
    countif(abs(need_83 - (need_80 + 0.3 * (need_90 - need_80))) > 0.01) as n_off,
    count(*) as n_rows,
from `teamster-332318.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__student_course_grades`
where need_83 is not null and academic_year = 2026
```

Expected: `n_off` is 0. The 80-to-90 derivation is an independent path to the
same value, so a 0 proves the affine identity holds on real rows.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml </dev/null
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__student_course_grades.yml
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target commit -m "feat(dbt): add need_83 to rpt_tableau__student_course_grades

Refs #5768

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Roster columns on `rpt_gsheets__gpa_roster`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__gpa_roster.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__gpa_roster.yml`

**Interfaces:**

- Consumes: Task 1 (`pace_status`, `gpa_needed_unweighted`,
  `gpa_needed_weighted`, `target_letter_grade`, `target_cutoff_percent`), Task 2
  (`course_name`, `y1_percent_current`, `is_below_target`, `is_locked`), Task 3
  (`course_name`, `pace_percent_to_next`, `next_letter_grade`,
  `quickest_win_rank`).
- Produces: roster columns `pace_status string`,
  `gpa_needed_unweighted float64`, `gpa_needed_weighted float64`,
  `target_letter_grade string`, `target_cutoff_percent float64`,
  `n_courses_below_target int64`, `courses_below_target string`,
  `quickest_win_course string`, `quickest_win_pace_percent float64`,
  `quickest_win_next_letter string`.

- [ ] **Step 1: Add the student-grain aggregations**

Add two CTEs before `roster` and join them in. The roster is one row per student
across all grades 5 and up; the new columns are NULL below high school because
Task 1 filters to HS.

```sql
    below_target as (
        select
            studentid,
            _dbt_source_project,

            countif(is_below_target and not is_locked) as n_courses_below_target,
            string_agg(
                if(
                    is_below_target and not is_locked,
                    concat(course_name, ' ', cast(y1_percent_current as string)),
                    null
                ),
                '; '
            ) as courses_below_target,
        from {{ ref("int_powerschool__course_pace") }}
        group by studentid, _dbt_source_project
    ),

    quickest_win as (
        select
            studentid,
            _dbt_source_project,
            course_name as quickest_win_course,
            pace_percent_to_next as quickest_win_pace_percent,
            next_letter_grade as quickest_win_next_letter,
        from {{ ref("int_gpa__course_quickest_win") }}
        where quickest_win_rank = 1
    ),
```

`string_agg` ignores NULL elements, so the `if` leaves out courses at or above
target. BigQuery `string_agg` without `order by` is nondeterministic in element
order; that is acceptable for a display string and avoids the banned `order by`.

In the `roster` CTE, add after the `gc.` columns:

```sql
            t.pace_status,
            t.gpa_needed_unweighted,
            t.gpa_needed_weighted,
            t.target_letter_grade,
            t.target_cutoff_percent,

            bt.n_courses_below_target,
            bt.courses_below_target,

            qw.quickest_win_course,
            qw.quickest_win_pace_percent,
            qw.quickest_win_next_letter,
```

and the joins after the `gc` join:

```sql
        left join
            {{ ref("int_powerschool__student_y1_target") }} as t
            on co.studentid = t.studentid
            and co.schoolid = t.schoolid
            and co._dbt_source_project = t._dbt_source_project
        left join
            below_target as bt
            on co.studentid = bt.studentid
            and co._dbt_source_project = bt._dbt_source_project
        left join
            quickest_win as qw
            on co.studentid = qw.studentid
            and co._dbt_source_project = qw._dbt_source_project
```

In the final select, after `cumulative_y1_gpa_projected,`:

```sql
    pace_status,
    gpa_needed_unweighted,
    gpa_needed_weighted,
    target_letter_grade,
    target_cutoff_percent,
    n_courses_below_target,
    courses_below_target,
    quickest_win_course,
    quickest_win_pace_percent,
    quickest_win_next_letter,
```

The `pivot` at the end of the model groups by every non-pivoted column, so the
new columns ride through unchanged.

- [ ] **Step 2: Add the contract columns**

Append to `columns:` in the yml, before `salesforce_contact_id`:

```yaml
- name: pace_status
  data_type: string
  description:
    on_pace, not_on_pace, goal_not_attainable, or unknown. High school only.
  config:
    meta:
      contains_pii: true
- name: gpa_needed_unweighted
  data_type: float64
  description:
    Unweighted Y1 GPA needed this year to finish at a 3.0 unweighted cumulative.
  config:
    meta:
      contains_pii: true
- name: gpa_needed_weighted
  data_type: float64
  description:
    The same target on the weighted scale PowerSchool shows, for reconciliation.
  config:
    meta:
      contains_pii: true
- name: target_letter_grade
  data_type: string
  description:
    Lowest letter in every GPA course that reaches the needed GPA, floored at B.
  config:
    meta:
      contains_pii: true
- name: target_cutoff_percent
  data_type: float64
  config:
    meta:
      contains_pii: true
- name: n_courses_below_target
  data_type: int64
  config:
    meta:
      contains_pii: true
- name: courses_below_target
  data_type: string
  description:
    Course name and current Y1 percent for each unlocked course below the
    target, separated by semicolons.
  config:
    meta:
      contains_pii: true
- name: quickest_win_course
  data_type: string
  description:
    The course where the fewest percent points this year buy the biggest
    unweighted grade-point gain.
  config:
    meta:
      contains_pii: true
- name: quickest_win_pace_percent
  data_type: float64
  description:
    Percent needed in each remaining term of that course to reach its next
    letter.
  config:
    meta:
      contains_pii: true
- name: quickest_win_next_letter
  data_type: string
  config:
    meta:
      contains_pii: true
```

- [ ] **Step 3: Build and check**

Run:

```bash
uv run dbt build --select int_powerschool__student_y1_target int_powerschool__course_pace int_gpa__course_quickest_win rpt_gsheets__gpa_roster --exclude resource_type:unit_test --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 20
```

Expected: four models build, tests pass.

Through the BigQuery MCP (aggregates only):

```sql
select
    pace_status,
    count(*) as n,
    countif(quickest_win_course is not null) as n_with_win,
    round(avg(n_courses_below_target), 2) as avg_below,
from `teamster-332318.zz_anthonygwalters_kipptaf_extracts.rpt_gsheets__gpa_roster`
where grade_level >= 9
group by pace_status
```

Expected: every high school row has a non-null `pace_status`; `unknown` is 0 or
a handful (scale 874 students); rows below grade 9 are NULL (query them
separately to confirm the count equals the pre-change middle school count).

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__gpa_roster.sql src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__gpa_roster.yml </dev/null
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target add src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__gpa_roster.sql src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__gpa_roster.yml
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target commit -m "feat(dbt): add quarter target, pace status, and quickest win to the GPA roster

Refs #5768

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Monitor columns on `rpt_tableau__gpa_goal_progress`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goal_progress.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_goal_progress.yml`

**Interfaces:**

- Consumes: Task 1 (`pace_status`, `gpa_needed_weighted`, `target_letter_grade`,
  `target_cutoff_percent`), Task 5's `below_target` shape (recomputed here from
  Task 2, not shared).
- Produces: `pace_status string`, `gpa_needed_weighted float64`,
  `target_letter_grade string`, `target_cutoff_percent float64`,
  `n_courses_below_target int64` on the current-year row.

- [ ] **Step 1: Add the join and columns**

The model is a wrapper with a header comment that says every added column must
go in both the select list and the contract. Add a CTE at the top:

```sql
with
    below_target as (
        select
            studentid,
            _dbt_source_project,

            countif(is_below_target and not is_locked) as n_courses_below_target,
        from {{ ref("int_powerschool__course_pace") }}
        group by studentid, _dbt_source_project
    )
```

Add after the four `gd.` columns:

```sql
    t.pace_status,
    t.gpa_needed_weighted,
    t.target_letter_grade,
    t.target_cutoff_percent,

    bt.n_courses_below_target,
```

Add the joins after the `gd` join. Both are restricted to the current-year row
so past-year rows stay NULL:

```sql
left join
    {{ ref("int_powerschool__student_y1_target") }} as t
    on cy.studentid = t.studentid
    and cy.schoolid = t.schoolid
    and cy._dbt_source_project = t._dbt_source_project
    and cy.academic_year = {{ var("current_academic_year") }}
left join
    below_target as bt
    on cy.studentid = bt.studentid
    and cy._dbt_source_project = bt._dbt_source_project
    and cy.academic_year = {{ var("current_academic_year") }}
```

- [ ] **Step 2: Add the contract columns**

```yaml
- name: pace_status
  data_type: string
  description:
    on_pace, not_on_pace, goal_not_attainable, or unknown. Current-year rows
    only.
  config:
    meta:
      contains_pii: true
- name: gpa_needed_weighted
  data_type: float64
  description:
    The needed GPA on the weighted scale PowerSchool shows. Current-year rows
    only.
  config:
    meta:
      contains_pii: true
- name: target_letter_grade
  data_type: string
  config:
    meta:
      contains_pii: true
- name: target_cutoff_percent
  data_type: float64
  config:
    meta:
      contains_pii: true
- name: n_courses_below_target
  data_type: int64
  config:
    meta:
      contains_pii: true
```

- [ ] **Step 3: Build and check the grain**

Run:

```bash
uv run dbt build --select rpt_tableau__gpa_goal_progress --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 15
```

Expected: the error-level uniqueness test on student and year passes. A failure
here means one of the joins fanned out; both intermediates are unique on the
join keys by their own tests, so check that the `academic_year` restriction is
on both joins.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goal_progress.sql src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_goal_progress.yml </dev/null
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_goal_progress.sql src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_goal_progress.yml
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target commit -m "feat(dbt): add pace status and quarter target to rpt_tableau__gpa_goal_progress

Refs #5768

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `rpt_tableau__gpa_course_pace` and its exposure

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_course_pace.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_course_pace.yml`
- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml` (the
  `academic_gradebook_health_suite` exposure's `depends_on`)

**Interfaces:**

- Consumes: Task 2 and Task 3, `int_extracts__student_enrollments` for roster
  fields.
- Produces: one row per student, course, and `_dbt_source_project` for the
  Monitor's course view.

- [ ] **Step 1: Write the model**

```sql
select
    co.academic_year,
    co.region,
    co.school,
    co.grade_level,
    co.student_number,
    co.student_name,
    co.advisory,
    co.school_leader_tableau_username,

    p.studentid,
    p.schoolid,
    p.course_number,
    p.course_name,
    p._dbt_source_project,
    p.potential_credit_hours,
    p.target_cutoff_percent,
    p.y1_percent_current,
    p.term_percent_current,
    p.pace_percent,
    p.is_below_target,
    p.is_secured,
    p.is_locked,

    qw.next_letter_grade,
    qw.next_cutoff_percent,
    qw.pace_percent_to_next,
    qw.quickest_win_rank,
from {{ ref("int_powerschool__course_pace") }} as p
inner join
    {{ ref("int_extracts__student_enrollments") }} as co
    on p.studentid = co.studentid
    and p.schoolid = co.schoolid
    and p._dbt_source_project = co._dbt_source_project
    and co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
left join
    {{ ref("int_gpa__course_quickest_win") }} as qw
    on p.studentid = qw.studentid
    and p.course_number = qw.course_number
    and p._dbt_source_project = qw._dbt_source_project
```

If `school_leader_tableau_username` is not on
`int_extracts__student_enrollments`, check
`rpt_tableau__gpa_cumulative_year.sql` for where the Monitor sources it and copy
that join; the column drives Tableau row-level security on the suite and must be
present.

- [ ] **Step 2: Write the properties file**

```yaml
models:
  - name: rpt_tableau__gpa_course_pace
    description: >-
      Course-grain companion to the Cumulative GPA Monitor: one row per
      current-year GPA course per high school student with the pace percent to
      the student's target letter, whether the course is below target, and its
      quickest-win rank.
    config:
      meta:
        contains_pii: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - studentid
              - course_number
              - _dbt_source_project
    columns:
      - name: academic_year
        data_type: int64
      - name: region
        data_type: string
      - name: school
        data_type: string
      - name: grade_level
        data_type: int64
      - name: student_number
        data_type: int64
      - name: student_name
        data_type: string
      - name: advisory
        data_type: string
      - name: school_leader_tableau_username
        data_type: string
      - name: studentid
        data_type: int64
      - name: schoolid
        data_type: int64
      - name: course_number
        data_type: string
      - name: course_name
        data_type: string
      - name: _dbt_source_project
        data_type: string
      - name: potential_credit_hours
        data_type: float64
      - name: target_cutoff_percent
        data_type: float64
      - name: y1_percent_current
        data_type: float64
      - name: term_percent_current
        data_type: float64
      - name: pace_percent
        data_type: float64
      - name: is_below_target
        data_type: boolean
      - name: is_secured
        data_type: boolean
      - name: is_locked
        data_type: boolean
      - name: next_letter_grade
        data_type: string
      - name: next_cutoff_percent
        data_type: float64
      - name: pace_percent_to_next
        data_type: float64
      - name: quickest_win_rank
        data_type: int64
```

Column descriptions live on the intermediates; this extract passes them through.
The model-level `contains_pii` covers the student-level content.

- [ ] **Step 3: Add the model to the exposure**

In `src/dbt/kipptaf/models/exposures/tableau.yml`, find the
`academic_gradebook_health_suite` exposure and add
`- ref("rpt_tableau__gpa_course_pace")` to its `depends_on` list.

- [ ] **Step 4: Build and check**

```bash
uv run dbt build --select rpt_tableau__gpa_course_pace --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target/src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 15
```

Expected: builds, uniqueness test passes.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_course_pace.sql src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_course_pace.yml src/dbt/kipptaf/models/exposures/tableau.yml </dev/null
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target add src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gpa_course_pace.sql src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gpa_course_pace.yml src/dbt/kipptaf/models/exposures/tableau.yml
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target commit -m "feat(dbt): add rpt_tableau__gpa_course_pace for the Cumulative GPA Monitor

Refs #5768

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Back-test and reference page

**Files:**

- Modify: `docs/models/academic-health-data-model.md` (the _Supporting models_
  section, after _The goal chain_)

**Interfaces:**

- Consumes: the dev-built models from Tasks 1 to 7.
- Produces: the back-test results, recorded in the PR body, and the reference
  page section.

- [ ] **Step 1: Run the pace sufficiency back-test**

Through the BigQuery MCP. For every student with a computable pace, plug the
pace into every remaining term and confirm the resulting credit-weighted
unweighted Y1 GPA clears the needed GPA. The pace lands every unlocked course
exactly on the target cutoff, so the resulting Y1 points are the target grade
points for unlocked courses and the live points for locked ones.

```sql
with per_course as (
  select p.studentid, p._dbt_source_project, p.potential_credit_hours,
    if(p.is_locked, p.y1_grade_points_unweighted_current, t.target_grade_points) as y1_points_if_paced
  from `teamster-332318.zz_anthonygwalters_kipptaf_gpa.int_powerschool__course_pace` p
  join `teamster-332318.zz_anthonygwalters_kipptaf_gpa.int_powerschool__student_y1_target` t
    on p.studentid = t.studentid and p.schoolid = t.schoolid and p._dbt_source_project = t._dbt_source_project
  where t.target_grade_points is not null
), per_student as (
  select studentid, _dbt_source_project,
    safe_divide(sum(potential_credit_hours * y1_points_if_paced), sum(potential_credit_hours)) as y1_if_paced
  from per_course group by 1, 2
)
select count(*) as n_students,
  countif(ps.y1_if_paced + 0.005 < t.gpa_needed_unweighted) as n_short,
  countif(ps.y1_if_paced + 0.005 < t.gpa_needed_unweighted and t.pace_status = 'not_on_pace') as n_short_not_on_pace
from per_student ps
join `teamster-332318.zz_anthonygwalters_kipptaf_gpa.int_powerschool__student_y1_target` t
  on ps.studentid = t.studentid and ps._dbt_source_project = t._dbt_source_project
```

Expected: `n_short_not_on_pace` is 0. `n_short` may be nonzero only for students
whose status is `goal_not_attainable` because a locked course drags the ceiling
below the need; record the number in the PR.

- [ ] **Step 2: Run the schedule-bump back-test**

```sql
select count(*) as n,
  countif(abs(gpa_needed_weighted - gpa_needed_unweighted - schedule_bump) > 0.011) as n_off,
  countif(schedule_bump = 0) as n_no_weighted,
  round(max(schedule_bump), 2) as max_bump
from `teamster-332318.zz_anthonygwalters_kipptaf_gpa.int_powerschool__student_y1_target`
```

Expected: `n_off` is 0, `n_no_weighted` is about 70 percent of `n`, `max_bump`
is below 1.0.

- [ ] **Step 3: Add the reference page section**

In `docs/models/academic-health-data-model.md`, after the _The goal chain_
subsection under _Supporting models_, add:

```markdown
### The quarter target chain

- `int_powerschool__student_y1_target`: one row per current-year high school
  student and school with the lowest unweighted letter whose grade points reach
  the needed GPA, floored at B; the weighted GPA that target corresponds to on
  the student's own schedule; and a pace status of `on_pace`, `not_on_pace`,
  `goal_not_attainable`, or `unknown`. It reads the needed GPA and attainability
  from `int_powerschool__gpa_cumulative`.
- `int_powerschool__course_pace`: one row per current-year GPA course per
  student with the average percent needed in each remaining term for the course
  Y1 to land on the target cutoff. The in-progress term is a remaining term, so
  the pace moves only when a term closes. A course whose terms have all ended is
  locked and has no pace.
- `int_gpa__course_quickest_win`: ranks each student's unlocked courses by grade
  points gained at the next letter times credits, over the percent gap to that
  letter's pace. Rank 1 is the course where the fewest points buy the most GPA.

These reach the GPA roster sheet, the Cumulative GPA Monitor through
`rpt_tableau__gpa_goal_progress`, and the course view through
`rpt_tableau__gpa_course_pace`. A quarter GPA target is deliberately absent:
quarter GPAs do not average to the Y1 GPA, and course percents do.
```

Also add `need_83` to the _Bands and flags_ table row for `need_60` to
`need_90`: change it to `need_60` to `need_90`, `need_83`, `need_next`.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/models/academic-health-data-model.md </dev/null
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target add docs/models/academic-health-data-model.md
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target commit -m "docs(models): document the GPA quarter target chain

Refs #5768

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Push and open the PR

- [ ] **Step 1: Run every unit test in the gpa folder and the touched extracts**

```bash
uv run dbt test --select "test_type:unit,gpa" --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 15
```

Expected: every unit test under `models/gpa/` passes, including the three
pre-existing ones.

- [ ] **Step 2: Push**

```bash
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-gpa-quarter-target push
```

- [ ] **Step 3: Open the PR**

Use `mcp__github__create_pull_request` with base `main`, the body from
`.github/pull_request_template.md`, `Closes #5768` in the body, the two
back-test results from Task 8 in the For Claude fold-out, and the attribution
line. Title:
`feat(dbt): per-course quarter target, quickest win, and pace status for the GPA roster`.
Then offer to watch CI and respond to the review, per the project's PR rules.
