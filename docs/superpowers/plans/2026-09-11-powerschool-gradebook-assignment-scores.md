# PowerSchool Gradebook Assignment Scores Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `int_powerschool__gradebook_assignments_scores` out of kipptaf
into the `powerschool` package, dropping the `region` and `credit_type` columns,
with a kipptaf `union_relations` wrapper over the three NJ regions above it.

**Architecture:** The package model carries every join internal to PowerSchool —
`int_powerschool__gradebook_assignments` to
`base_powerschool__course_enrollments` to `stg_powerschool__assignmentscore` —
and all 39 derived columns. All three refs already have a package copy, so the
`from` and `join` clause text is unchanged; only the resolution target moves.
The kipptaf model becomes a bare `union_relations` wrapper plus
`extract_source_project()`, matching `int_powerschool__gradebook_assignments`
one layer up in the same directory. All three enabled consumers read the wrapper
at the same name and need no edit.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, `uv` for every dbt invocation,
trunk for lint, BigQuery MCP for verification.

## Global Constraints

- Spec:
  `docs/superpowers/specs/2026-09-11-powerschool-gradebook-assignment-scores-design.md`.
  Read it before Task 1.
- Worktree:
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores`.
  Every path in this plan is relative to it. Every `git` call is
  `git -C <worktree>`.
- Never run bare `python`, `dbt`, or `dagster`. Always `uv run`.
- dbt from a worktree:
  `uv run dbt <cmd> --project-dir <worktree>/src/dbt/<project>`. Never
  `uv --directory <worktree> run dbt` — that sets cwd to the worktree root,
  where no `dbt_project.yml` exists.
- The `powerschool` project is never run standalone. Parse and compile it
  through a consuming district: `kippnewark`, `kippcamden`, or `kipppaterson`.
  `kippmiami` does not consume the package and is not involved in this change.
- Open every file under `src/dbt/` with Read/Edit/Write, never `cat` — the
  path-scoped rule files load on a Read match and not on a Bash string.
- Lint before every push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree. MD060 on a widened markdown table clears when
  the commit fmt hook re-pads it; do not hand-align.
- Column order in the moved SQL must not change. sqlfluff ST06 passes on the
  current order and the five deletions do not disturb it.
- `git add -u` for tracked files. A NEW file must be named explicitly on
  `git add` — `-u` does not stage untracked paths.
- Commit messages end with:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- If a `git commit -m` is hook-blocked, `rm -f .claude/scratch/commit-msg.txt`,
  Write the message there, then `git commit -F .claude/scratch/commit-msg.txt`.
- PII tags carry over from the kipptaf model exactly as they are:
  `contains_pii: true` on `student_number` and `teacher_name`, nothing else.
  Widening to the full tier-3 set in `.claude/rules/ferpa-pii.md` (the score and
  grade columns) is a separate decision and is out of scope for a move.

## File Structure

| File                                                                                                           | Responsibility                                                         |
| -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql`                | Create. The PowerSchool-internal join and all 39 derived columns.      |
| `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml`     | Create. Column types, descriptions, and the composite uniqueness test. |
| `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`            | Replace. 200 lines become a `union_relations` wrapper.                 |
| `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml` | Modify. Add `_dbt_source_project` and the columns it never declared.   |
| `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`                                                    | Modify. Add the table entry.                                           |
| `src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml`                                                    | Modify. Add the table entry.                                           |
| `src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml`                                                  | Modify. Add the table entry.                                           |
| `docs/models/gradebook-audit-data-model.md`                                                                    | Audit only. Correct any claim about which project the model lives in.  |

---

## Task 1: The package model

**Files:**

- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml`

**Interfaces:**

- Consumes: `int_powerschool__gradebook_assignments` (`assignmentsectionid`,
  `sectionsdcid`, `assignmentid`, `name`, `duedate`, `scoretype`,
  `totalpointvalue`, `category_name`, `category_code`, `iscountedinfinalgrade`),
  `base_powerschool__course_enrollments` (`sections_dcid`, `cc_dateenrolled`,
  `cc_dateleft`, `is_dropped_section`, `cc_academic_year`, `students_dcid`,
  `students_student_number`, `courses_course_name`, `teacher_lastfirst`,
  `cc_schoolid`, `sections_grade_level`, `school_level`),
  `stg_powerschool__assignmentscore` (`assignmentsectionid`, `studentsdcid`,
  `scorepoints`, `actualscoreentered`, `islate`, `isexempt`, `ismissing`).
- Produces: a relation with 39 columns, grain one row per
  `(assignmentsectionid, students_dcid)`. Tasks 2 and 3 depend on these exact
  names. The full ordered list is in Step 2's yml.

- [ ] **Step 1: Write the model SQL**

This is the current kipptaf SQL with five deletions and nothing else changed.
Write
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql`:

```sql
with
    scores as (
        select
            a.assignmentsectionid,
            a.sectionsdcid,
            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,
            a.category_name,
            a.category_code,
            a.iscountedinfinalgrade,

            s.scorepoints,
            s.actualscoreentered,

            e.cc_academic_year as academic_year,
            e.students_dcid,
            e.students_student_number as student_number,
            e.courses_course_name as course_name,
            e.teacher_lastfirst as teacher_name,

            coalesce(s.islate, 0) as is_late,
            coalesce(s.isexempt, 0) as is_exempt,
            coalesce(s.ismissing, 0) as is_missing,

            case
                when coalesce(s.isexempt, 0) = 1
                then false
                when a.iscountedinfinalgrade = 0
                then false
                else true
            end as is_expected,

            /* hardcoding year while we look for a better solution to custom grade
               level vs school level */
            if(
                e.cc_academic_year >= 2025
                and e.cc_schoolid = 179905
                and e.sections_grade_level >= 5,
                'MS',
                e.school_level
            ) as school_level_alt,

            if(
                a.scoretype = 'POINTS',
                s.scorepoints,
                safe_cast(s.actualscoreentered as numeric)
            ) as score_entered,

            if(a.scoretype = 'POINTS', s.scorepoints, null) as points_earned,

            if(
                a.scoretype in ('PERCENT', 'GRADESCALE', 'COLLECTED'),
                safe_cast(s.actualscoreentered as float64),
                null
            ) as numeric_grade_earned,

            if(
                a.scoretype = 'POINTS',
                round(safe_divide(s.scorepoints, a.totalpointvalue) * 100, 2),
                safe_cast(s.actualscoreentered as numeric)
            ) as assign_final_score_percent,

            (a.totalpointvalue / 2) as half_total_point_value,

        from {{ ref("int_powerschool__gradebook_assignments") }} as a
        /* PS automatically assigns ALL assignments to a student when they enroll into
        a section, including those from before their enrollment date. This join ensures
        assignments are only matched to valid student enrollments */
        inner join
            {{ ref("base_powerschool__course_enrollments") }} as e
            on a.sectionsdcid = e.sections_dcid
            and a.duedate >= e.cc_dateenrolled
            and a.duedate < e.cc_dateleft
            and not e.is_dropped_section
        left join
            {{ ref("stg_powerschool__assignmentscore") }} as s
            on a.assignmentsectionid = s.assignmentsectionid
            and e.students_dcid = s.studentsdcid
    ),

    assignment_coding as (
        select
            assignmentsectionid,
            sectionsdcid,
            assignmentid,
            assignment_name,
            duedate,
            scoretype,
            totalpointvalue,
            category_name,
            category_code,
            iscountedinfinalgrade,
            scorepoints,
            actualscoreentered,
            academic_year,
            students_dcid,
            student_number,
            course_name,
            teacher_name,
            is_late,
            is_exempt,
            is_missing,
            is_expected,
            school_level_alt,
            score_entered,
            points_earned,
            numeric_grade_earned,
            assign_final_score_percent,
            half_total_point_value,

            if(is_expected and score_entered = 0, 1, 0) as is_expected_zero,

            if(
                is_expected
                and score_entered = 0
                and school_level_alt = 'HS'
                and is_missing = 0,
                1,
                0
            ) as is_expected_academic_dishonesty,

            if(is_expected and score_entered is null, 1, 0) as is_expected_null,

            if(is_expected and is_late = 1, 1, 0) as is_expected_late,

            if(is_expected and is_missing = 1, 1, 0) as is_expected_missing,

            if(
                is_expected and score_entered is not null, true, false
            ) as is_expected_scored,

        from scores
    )

select
    *,

    if(
        is_expected and score_entered > totalpointvalue, true, false
    ) as assign_score_above_max,

    if(
        category_code in ('H', 'W', 'F')
        and is_expected
        and is_missing = 0
        and score_entered < 5,
        true,
        false
    ) as assign_mh_hwf_score_less_5,

    if(
        category_code in ('H', 'W', 'F')
        and school_level_alt = 'MS'
        and is_expected_missing = 1
        and score_entered != 5,
        true,
        false
    ) as assign_ms_hwf_missing_score_not_5,

    if(
        category_code in ('H', 'W', 'F', 'S')
        and school_level_alt = 'HS'
        and is_expected_missing = 1
        and score_entered != 0,
        true,
        false
    ) as assign_hs_hwfs_missing_score_not_0,

    if(
        category_code = 'S'
        and school_level_alt = 'MS'
        and is_expected
        and score_entered < half_total_point_value,
        true,
        false
    ) as assign_ms_s_score_less_50p,

    if(
        category_code = 'S'
        and school_level_alt = 'HS'
        and is_expected
        and is_missing = 0
        and score_entered < half_total_point_value,
        true,
        false
    ) as assign_hs_s_score_less_50p,

from assignment_coding
```

Diff this against the kipptaf original before moving on. Exactly five things are
gone and nothing else: `a._dbt_source_project` from the `scores` select list,
`_dbt_source_project` from the `assignment_coding` select list,
`and a._dbt_source_project = e._dbt_source_project`,
`and a._dbt_source_project = s._dbt_source_project`, and the two `region` /
`credit_type` pairs (`{{ extract_region("a") }} as region` plus
`e.courses_credittype as credit_type` in `scores`, and the bare `region` and
`credit_type` entries in `assignment_coding`). The two inline comments stay
verbatim — they explain the enrollment join and the `school_level_alt` hardcode,
which a reader of those lines cannot otherwise see.

- [ ] **Step 2: Write the properties yml**

Write
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml`:

```yaml
models:
  - name: int_powerschool__gradebook_assignments_scores
    description: >-
      One row per PowerSchool gradebook assignment per student expected to have
      a score for it, with the score itself where one was entered and a set of
      derived flags describing whether the score is present, late, missing,
      exempt, or out of range for its gradebook category.


      Assignments are matched to students through the course enrollment active
      when the assignment was due, on a half-open date range. PowerSchool
      assigns every assignment in a section to a student on enrollment,
      including assignments due before they arrived, so the range join is what
      scopes each assignment to a real enrollment. Dropped sections are
      excluded. The score join is a left join, so a row exists for an expected
      assignment with no score entered, and the score columns are null there.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - assignmentsectionid
              - students_dcid
    columns:
      - name: assignmentsectionid
        data_type: int64
        description:
          Primary key. Unique sequential number generated by the application.
          Required. Indexed.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentsection
            source_column: assignmentsectionid
            column_role: primary_key
      - name: sectionsdcid
        data_type: int64
        description:
          Foreign key. Internal number for the associated sections.DCID record.
          Required. Indexed.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentsection
            source_column: sectionsdcid
            column_role: foreign_key
      - name: assignmentid
        data_type: int64
        description:
          Foreign key. Internal number for the associated Assignment.ID record.
          Required. Indexed.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentsection
            source_column: assignmentid
            column_role: foreign_key
      - name: assignment_name
        data_type: string
        description: Name the teacher gave the assignment in the gradebook.
      - name: duedate
        data_type: date
        description:
          The date the assignment is due. Defaults to Default is the system date
          + 1 day. Indexed.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentsection
            source_column: duedate
      - name: scoretype
        data_type: string
        description: Indicates if this score is a letter grade or percent.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentsection
            source_column: scoretype
      - name: totalpointvalue
        data_type: float64
        description:
          This is the total weighted points that the assignment is worth. If the
          entry points are 25, and theweight is 4, then the total point value is
          100.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentsection
            source_column: totalpointvalue
      - name: category_name
        data_type: string
        description: >-
          Name of the gradebook category the assignment belongs to, resolved
          from the district category where one exists and the teacher category
          otherwise.
      - name: category_code
        data_type: string
        description: >-
          First letter of the category name, upper-cased. The flag logic reads
          it rather than the full name, with H, W, F and S carrying the
          category-specific score rules.
      - name: iscountedinfinalgrade
        data_type: int64
        description:
          "Indicates if the assignment will count toward the final grade. Valid
          values: 0=Does not count towardfinal grade, 1=Counts toward final
          grade. Defaults to 1. Required."
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentsection
            source_column: iscountedinfinalgrade
      - name: scorepoints
        data_type: float64
        description: Indicates the number of points for a score.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentscore
            source_column: scorepoints
      - name: actualscoreentered
        data_type: string
        description:
          Identifies the score entered for this assignment. This field may be
          Null.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentscore
            source_column: actualscoreentered
      - name: academic_year
        data_type: int64
        description: >-
          Academic year of the course enrollment the assignment was matched to,
          expressed as the starting calendar year.
        config:
          meta:
            source_system: PowerSchool
            source_model: base_powerschool__course_enrollments
            source_column: cc_academic_year
      - name: students_dcid
        data_type: int64
        description: >-
          Durable internal key of the student the row belongs to, and the second
          half of this model's grain.
        config:
          meta:
            source_system: PowerSchool
            source_model: base_powerschool__course_enrollments
            source_column: students_dcid
            column_role: foreign_key
      - name: student_number
        data_type: int64
        description:
          Student number of the student the assignment row belongs to. Carried
          through from the course-enrollment join so consumers do not re-derive
          it.
        config:
          meta:
            source_system: PowerSchool
            source_model: base_powerschool__course_enrollments
            source_column: students_student_number
            contains_pii: true
      - name: course_name
        data_type: string
        description: Name of the course the assignment's section belongs to.
        config:
          meta:
            source_system: PowerSchool
            source_model: base_powerschool__course_enrollments
            source_column: courses_course_name
      - name: teacher_name
        data_type: string
        description: Teacher of record for the assignment's section, last-first.
        config:
          meta:
            source_system: PowerSchool
            source_model: base_powerschool__course_enrollments
            source_column: teacher_lastfirst
            contains_pii: true
      - name: is_late
        data_type: int64
        description: >-
          The gradebook's late marker, zero-filled where no score row exists.
      - name: is_exempt
        data_type: int64
        description: >-
          The gradebook's exempt marker, zero-filled where no score row exists.
      - name: is_missing
        data_type: int64
        description: >-
          The gradebook's missing marker, zero-filled where no score row exists.
      - name: is_expected
        data_type: boolean
        description: >
          True when the student is expected to have a score for this assignment:
          not exempt and counted in final grade. False otherwise.
      - name: school_level_alt
        data_type: string
        description: >-
          School level of the enrollment, overridden to MS for grade 5 and above
          at one Camden school from academic year 2025 forward, where the custom
          grade level and the school level disagree. Every other row carries the
          school level unchanged.
      - name: score_entered
        data_type: float64
        description: >-
          The score as a number, whatever the score type. Points-scored for
          POINTS assignments and the entered value cast to numeric otherwise.
          Null when no score was entered.
      - name: points_earned
        data_type: float64
        description: >-
          Raw points scored, populated only when source `scoretype = POINTS`
          (NULL for PERCENT/GRADESCALE/COLLECTED). Ed-Fi studentGradebookEntry
          `points_earned`.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentscore
            source_column: scorepoints
      - name: numeric_grade_earned
        data_type: float64
        description: >-
          Numeric grade scored (0-100 percent or letter-grade equivalent),
          populated only when source `scoretype` is `PERCENT`, `GRADESCALE`, or
          `COLLECTED` (NULL for POINTS). Ed-Fi studentGradebookEntry
          `numeric_grade_earned`.
        config:
          meta:
            source_system: PowerSchool
            source_model: stg_powerschool__assignmentscore
            source_column: actualscoreentered
      - name: assign_final_score_percent
        data_type: float64
        description: >-
          The score as a percentage of the total point value for POINTS
          assignments, rounded to two places, and the entered value cast to
          numeric for every other score type.
      - name: half_total_point_value
        data_type: float64
        description: >-
          Half the assignment's total point value, the threshold the two
          fifty-percent category flags compare against.
      - name: is_expected_zero
        data_type: int64
        description: Conditional on is_expected, score_entered.
      - name: is_expected_academic_dishonesty
        data_type: int64
        description:
          Conditional on is_expected, is_missing, school_level_alt,
          score_entered.
      - name: is_expected_null
        data_type: int64
        description: Conditional on is_expected, score_entered.
      - name: is_expected_late
        data_type: int64
        description: Conditional on is_expected, is_late.
      - name: is_expected_missing
        data_type: int64
        description: Conditional on is_expected, is_missing.
      - name: is_expected_scored
        data_type: boolean
        description: Conditional on is_expected, score_entered.
      - name: assign_score_above_max
        data_type: boolean
        description: True when score_entered exceeds totalpointvalue.
      - name: assign_mh_hwf_score_less_5
        data_type: boolean
        description: >-
          H, W, or F category assignment where is_expected_missing = 0 and
          score_entered < 5. Consolidates the three per-category flags
          assign_w_score_less_5, assign_h_score_less_5, and
          assign_f_score_less_5.
      - name: assign_ms_hwf_missing_score_not_5
        data_type: boolean
        description: >-
          H, W, or F category MS assignment marked missing where score_entered
          != 5. Consolidates assign_w_missing_score_not_5,
          assign_h_missing_score_not_5, and assign_f_missing_score_not_5.
      - name: assign_hs_hwfs_missing_score_not_0
        data_type: boolean
        description: >-
          H, W, F, or S category HS assignment marked missing where
          score_entered != 0. Consolidates assign_w_missing_score_not_0,
          assign_h_missing_score_not_0, assign_f_missing_score_not_0, and
          assign_s_missing_score_not_0.
      - name: assign_ms_s_score_less_50p
        data_type: boolean
        description: >-
          S category MS assignment where score_entered < half_total_point_value.
          Renamed from assign_s_score_less_50p, now explicitly MS-scoped.
      - name: assign_hs_s_score_less_50p
        data_type: boolean
        description: >-
          S category HS assignment, not missing, where score_entered <
          half_total_point_value. Renamed from assign_s_hs_score_less_50p.
```

- [ ] **Step 3: Confirm no district disables any input**

The new model needs all three inputs enabled in every NJ district. Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores && \
grep -nE 'gradebook_assignments|assignmentscore|assignmentsection|assignmentcategoryassoc|teachercategory|districtteachercategory|course_enrollments' \
  src/dbt/kippnewark/dbt_project.yml src/dbt/kippcamden/dbt_project.yml \
  src/dbt/kipppaterson/dbt_project.yml || echo "NONE DISABLED — correct"
```

Expected: `NONE DISABLED — correct`. Any hit means that input is disabled in
that district and the model cannot build there — stop and report it.

- [ ] **Step 4: Verify it parses**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores/src/dbt/kippnewark
```

Expected: `Performance info` and no error. A `Compilation Error` naming
`int_powerschool__gradebook_assignments_scores` means a `ref()` typo.

- [ ] **Step 5: Verify it compiles, and that the refs resolved to the package**

```bash
uv run dbt compile --select int_powerschool__gradebook_assignments_scores --target dev \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores/src/dbt/kippnewark
```

Expected: `Compiled node 'int_powerschool__gradebook_assignments_scores'`. Read
the compiled SQL and confirm all three relations resolved inside a
`kippnewark_powerschool`-shaped dataset, and that no `_dbt_source_project`
reference and no `region` or `credit_type` column survive:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores && \
grep -cE '_dbt_source_project|extract_region| as region,| as credit_type,' \
  src/dbt/kippnewark/target/compiled/kippnewark/models/powerschool/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql
```

Expected: `0`. A non-zero count means a deletion was missed.

- [ ] **Step 6: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml </dev/null
```

Expected: `No issues`. An ST06 failure means Step 1's column order was changed —
restore it rather than reordering to satisfy the linter.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores add \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores commit -m "feat(powerschool): add int_powerschool__gradebook_assignments_scores

Carries the gradebook assignment to course enrollment to assignment score
join that kipptaf rebuilt, plus all 39 derived columns. The region and
credit_type columns are dropped; neither had an enabled reader.

Refs #5260

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: The kipptaf wrapper and its NJ sources

**Files:**

- Replace:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml`

**Interfaces:**

- Consumes: Task 1's package model, materialized per district.
- Produces: `int_powerschool__gradebook_assignments_scores` in kipptaf, carrying
  all 39 Task 1 columns plus `_dbt_source_project STRING`. The three enabled
  consumers already read exactly these names and are not edited.

- [ ] **Step 1: Replace the kipptaf model with the wrapper**

Overwrite
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`
entirely with:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kipppaterson_powerschool", model.name),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,

from union_relations as ur
```

Two siblings in this directory supply the shape.
`int_powerschool__gradebook_assignments.sql` is where the aliased `ur` form of
the `select` and the macro call comes from;
`int_powerschool__section_teachers.sql` is where the shorter `model.name`
relation form comes from. Both forms are in the repo and both are correct — the
wrapper above uses one of each. Miami is deliberately absent and stays absent:
`kippmiami` does not consume the `powerschool` package and this model is NJ-only
by design.

- [ ] **Step 2: Update the wrapper's properties yml**

The existing yml declares 39 of the model's columns but is missing
`academic_year` and `_dbt_source_project`, and declares no `region` or
`credit_type` (which is why dropping them needs no yml edit). Make three changes
and leave everything else alone:

1. Keep the model-level `data_tests:` block exactly as it is — the composite
   `dbt_utils.unique_combination_of_columns` on `_dbt_source_project`,
   `assignmentsectionid`, `students_dcid` is still correct for the union.
2. Replace the model `description:` with one that says what the wrapper is:

   ```yaml
   description: >-
     Union of the per-region PowerSchool gradebook assignment-score models. One
     row per assignment per student expected to have a score for it, with the
     score where one was entered and the derived presence, timeliness and
     category flags.


     NJ-only by design: this unions the district PowerSchool packages, and
     Miami's gradebook is in Focus, not PowerSchool. No PowerSchool gradebook
     history for Miami is kept. The Focus gradebook branch is #5010. Ratified on
     #4996.
   ```

3. Add an `academic_year` entry and a `_dbt_source_project` entry. Put
   `academic_year` directly after `actualscoreentered`, matching the package
   model's order, and `_dbt_source_project` last:

   ```yaml
   - name: academic_year
     data_type: int64
     description: >-
       Academic year of the course enrollment the assignment was matched to,
       expressed as the starting calendar year.
   ```

   ```yaml
   - name: _dbt_source_project
     data_type: string
     description: District code location derived from _dbt_source_relation.
   ```

   The file currently opens its `columns:` list with a bare
   `- name: _dbt_source_project` / `data_type: string` pair and no
   `description:`. Delete that leading entry when you add the documented one at
   the end, so the column is declared once.

- [ ] **Step 3: Add the source entry to all three NJ source files**

In each of `sources-kippnewark.yml`, `sources-kippcamden.yml`, and
`sources-kipppaterson.yml`, add this block under `tables:` directly AFTER the
existing `int_powerschool__gradebook_assignments` entry, so the new model sits
beside its sibling. These files are not alphabetically sorted, so match the
neighbours rather than re-sorting. Substitute the district name on the
`asset_key` line — `kippnewark`, `kippcamden`, `kipppaterson`:

```yaml
- name: int_powerschool__gradebook_assignments_scores
  config:
    meta:
      dagster:
        group: powerschool
        asset_key:
          - kippnewark
          - powerschool
          - int_powerschool__gradebook_assignments_scores
```

In `sources-kippnewark.yml` the insertion point is after line 808. Locate the
equivalent point in the other two files by searching for
`int_powerschool__gradebook_assignments`; do not assume the same line number.

- [ ] **Step 4: Verify kipptaf parses**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores/src/dbt/kipptaf
```

Expected: success.
`Compilation Error ... depends on a source named ... which was not found` means
a source entry is missing or misnamed.

- [ ] **Step 5: Confirm the three consumers still resolve**

No consumer file changes, so this is a check, not an edit:

```bash
uv run dbt ls --select int_powerschool__gradebook_assignments_scores+1 \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores/src/dbt/kipptaf
```

Expected: the model plus `int_powerschool__gradebook_assignment_scores_rollup`,
`int_students__gradebook_assignments_scores`, and
`rpt_deanslist__missing_assignments`, and the model's own test. The three
disabled audit models must NOT appear — if one does, its `enabled: false` was
changed and the `region` / `credit_type` drop needs re-deciding before going
further.

- [ ] **Step 6: Confirm the wrapper's column list resolves**

A dev-target compile expands to nothing because no `zz_<user>_*` copy of a new
package model exists. Compile against staging, which reads the same `zz_stg_*`
relations dbt Cloud CI does. This is a read, not a warehouse write, so it needs
no authorization.

```bash
uv run dbt compile --select int_powerschool__gradebook_assignments_scores --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores/src/dbt/kipptaf
```

Expected before Task 4's seed: an EMPTY expansion, which still compiles clean.
That is why Task 4 exists. Re-run this step after Task 4 and confirm all 39
columns are listed across three union branches.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml \
  src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml \
  src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores add -u src/dbt/kipptaf
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores commit -m "refactor(kipptaf): union the NJ gradebook assignment-score package models

Replaces 200 lines of PowerSchool join and flag logic with a
union_relations wrapper. All three consumers read the same name and are
unchanged. The region and credit_type columns are gone; neither was
declared in the properties yml and neither had an enabled reader.

Refs #5260

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Prove behavior preservation against production

**Files:** none modified. This task runs comparisons.

**Interfaces:**

- Consumes: Task 1's package model, compiled but not built.
- Produces: evidence for the PR's Reviewer Notes. Nothing downstream depends on
  it, but a mismatch here blocks Task 4.

Why this shape: there is no `target/prod` manifest in any district checkout
(verified 2026-09-11 — all three are absent), so a `--defer --favor-state` build
is not available. And a dev build would be wrong anyway: kipptaf `source()`
resolves to personal `zz_<user>_*` copies under `target=dev`, and
`--favor-state` governs `ref()` but not `source()`. So compile the new model
against prod and run its SQL directly. `dbt compile --target prod` performs no
warehouse write and is not classifier-blocked.

- [ ] **Step 1: Compile the package model against prod, per district**

```bash
for d in kippnewark kippcamden kipppaterson; do
  uv run dbt compile --select int_powerschool__gradebook_assignments_scores --target prod \
    --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores/src/dbt/${d}
done
```

Expected: three successful compiles. The compiled file for each district is at
`src/dbt/<district>/target/compiled/<district>/models/powerschool/sis/intermediate/int_powerschool__gradebook_assignments_scores.sql`.
Read each one and confirm every relation is a `<district>_powerschool`
production path with no `zz_` prefix.

- [ ] **Step 2: Fingerprint both sides per district per academic year**

For each district, run this through the BigQuery MCP, pasting that district's
compiled SQL into the `new_form` CTE and substituting the district name in the
`_dbt_source_project` filter. The 39 columns are enumerated in a fixed order on
both sides so the row fingerprint is comparable; `to_json_string(struct(...))`
is NULL-safe, unlike `concat()`.

```sql
with
    new_form as (
        -- paste the district's compiled SQL here, unchanged
    ),

    new_fp as (
        select
            academic_year,
            count(*) as n_rows,
            sum(
                farm_fingerprint(
                    to_json_string(
                        struct(
                            assignmentsectionid, sectionsdcid, assignmentid,
                            assignment_name, duedate, scoretype, totalpointvalue,
                            category_name, category_code, iscountedinfinalgrade,
                            scorepoints, actualscoreentered, students_dcid,
                            student_number, course_name, teacher_name, is_late,
                            is_exempt, is_missing, is_expected, school_level_alt,
                            score_entered, points_earned, numeric_grade_earned,
                            assign_final_score_percent, half_total_point_value,
                            is_expected_zero, is_expected_academic_dishonesty,
                            is_expected_null, is_expected_late,
                            is_expected_missing, is_expected_scored,
                            assign_score_above_max, assign_mh_hwf_score_less_5,
                            assign_ms_hwf_missing_score_not_5,
                            assign_hs_hwfs_missing_score_not_0,
                            assign_ms_s_score_less_50p,
                            assign_hs_s_score_less_50p
                        )
                    )
                )
            ) as fp,
        from new_form
        group by academic_year
    ),

    old_fp as (
        select
            academic_year,
            count(*) as n_rows,
            sum(
                farm_fingerprint(
                    to_json_string(
                        struct(
                            assignmentsectionid, sectionsdcid, assignmentid,
                            assignment_name, duedate, scoretype, totalpointvalue,
                            category_name, category_code, iscountedinfinalgrade,
                            scorepoints, actualscoreentered, students_dcid,
                            student_number, course_name, teacher_name, is_late,
                            is_exempt, is_missing, is_expected, school_level_alt,
                            score_entered, points_earned, numeric_grade_earned,
                            assign_final_score_percent, half_total_point_value,
                            is_expected_zero, is_expected_academic_dishonesty,
                            is_expected_null, is_expected_late,
                            is_expected_missing, is_expected_scored,
                            assign_score_above_max, assign_mh_hwf_score_less_5,
                            assign_ms_hwf_missing_score_not_5,
                            assign_hs_hwfs_missing_score_not_0,
                            assign_ms_s_score_less_50p,
                            assign_hs_s_score_less_50p
                        )
                    )
                )
            ) as fp,
        from
            `teamster-332318`.kipptaf_powerschool.int_powerschool__gradebook_assignments_scores
        where _dbt_source_project = 'kippnewark'
        group by academic_year
    )

select
    coalesce(n.academic_year, o.academic_year) as academic_year,
    n.n_rows as new_rows,
    o.n_rows as old_rows,
    n.fp = o.fp as fp_match,
from new_fp as n
full join old_fp as o on n.academic_year = o.academic_year
order by academic_year
```

Expected: one row per academic year, `new_rows` equal to `old_rows`, and
`fp_match` true on every row. The `struct(...)` lists 38 columns, not 39:
`academic_year` is the `group by` key, so it is compared by the join rather than
inside the fingerprint. 38 plus `academic_year` covers all 39.

A row-count match with `fp_match` false means a value changed. A row-count
mismatch means the join changed. Either one blocks Task 4 — go to Step 3.

If the query fails with `Resources exceeded ... query is too complex` or the
nested-view limit, add `and academic_year = <year>` to both branches and run one
year at a time.

- [ ] **Step 3: Drill into any mismatching year**

Only if Step 2 reported a mismatch. For the failing district and year, replace
the final `select` with a two-directional set difference over the same 39
columns:

```sql
select 'new_minus_old' as direction, count(*) as n
from (
    select <the 39 columns> from new_form where academic_year = <year>
    except distinct
    select <the 39 columns>
    from `teamster-332318`.kipptaf_powerschool.int_powerschool__gradebook_assignments_scores
    where _dbt_source_project = '<district>' and academic_year = <year>
)

union all

select 'old_minus_new', count(*)
from (
    select <the 39 columns>
    from `teamster-332318`.kipptaf_powerschool.int_powerschool__gradebook_assignments_scores
    where _dbt_source_project = '<district>' and academic_year = <year>
    except distinct
    select <the 39 columns> from new_form where academic_year = <year>
)
```

Then sample 20 differing rows and diagnose. Do not proceed to Task 4 with an
unexplained difference.

One difference is expected and is NOT a defect: the prod kipptaf model reads
`int_powerschool__course_enrollments_union`, a TABLE that can lag the district
`base_powerschool__course_enrollments` relations. Measured 2026-09-11, that
staleness accounted for 23 Camden and 8 Paterson rows in the enrollment model
itself. If a small mismatch appears, check
`kipptaf_powerschool.__TABLES__.last_modified_time` for
`int_powerschool__course_enrollments_union` against the district base relation's
before treating it as a defect.

- [ ] **Step 4: Record the numbers**

Write the per-district, per-year table to
`.claude/scratch/gradebook-scores-verification.md` for the PR body. No commit —
`.claude/scratch/` is gitignored.

---

## Task 4: Seed staging, then push and open the PR

**Files:** none modified.

**Interfaces:**

- Consumes: Tasks 1 through 3.
- Produces:
  `zz_stg_<district>_powerschool.int_powerschool__gradebook_assignments_scores`
  in the three NJ districts, so dbt Cloud CI can resolve the new source.

- [ ] **Step 1: Get authorization for the staging seed**

This writes shared `zz_stg_*` tables other developers and CI read. Ask the user
in plain text for explicit go-ahead in the immediately-preceding turn, and do
not proceed without it. The consent classifier reads only the assistant message
before the tool call, never an `AskUserQuestion` answer.

- [ ] **Step 2: Seed the three NJ districts**

Run serially, not in parallel — parallel runs across projects exhaust BigQuery's
`INFORMATION_SCHEMA.simple_rate.user` quota:

```bash
for d in kippnewark kippcamden kipppaterson; do
  uv run dbt build --select int_powerschool__gradebook_assignments_scores --target staging \
    --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores/src/dbt/${d}
done
```

Expected: three successful builds, each with its
`dbt_utils.unique_combination_of_columns` test passing. A build that fails on a
missing upstream column means that district's `zz_stg_*` copies are stale;
`dbt clone --select <upstream> --target staging` for that district first, which
also needs authorization.

- [ ] **Step 3: Re-run Task 2 Step 6 and confirm the columns resolve**

```bash
uv run dbt compile --select int_powerschool__gradebook_assignments_scores --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores/src/dbt/kipptaf
```

Expected: the compiled SQL now lists all 39 columns across three union branches.
An empty expansion means Step 2 did not land.

- [ ] **Step 4: Confirm the three consumers compile against the wrapper**

```bash
uv run dbt compile --target staging \
  --select int_powerschool__gradebook_assignment_scores_rollup int_students__gradebook_assignments_scores rpt_deanslist__missing_assignments \
  --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores/src/dbt/kipptaf
```

Expected: three compiles, no error. A `Name <col> not found` here means the
wrapper dropped a column a consumer reads — stop and diagnose rather than
editing the consumer.

- [ ] **Step 5: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores push -u origin cbini/refactor/claude-powerschool-gradebook-scores
```

- [ ] **Step 6: Open the PR**

Open it with `mcp__github__create_pull_request`, body from
`.github/pull_request_template.md`, `Refs #5260` in the body. Write one line per
paragraph — GitHub renders every newline as a break, so do not hard-wrap.

Record in Reviewer Notes: the Task 3 per-district fingerprint results, the
staging seed that was run, that `region` and `credit_type` were dropped with
zero enabled readers, and that row 6 of #5260 closed by inspection with no code
change.

Then verify the stored body matches intent — a malformed parameter succeeds with
the wrong payload:

```bash
gh api repos/TEAMSchools/teamster/pulls/<n> --jq .body
```

- [ ] **Step 7: Watch CI**

Invoke `pr-ci-review`. Arm the Monitor in the same turn you say you will watch.
Expect `state:modified+` to pull the whole descendant graph of the wrapper into
CI, so budget for pre-existing warn-test noise unrelated to this change.

---

## Task 5: Documentation audit

Severable. It changes no dbt model and can ship as its own commit on this branch
or be dropped.

**Files:**

- Audit, and modify only if wrong: `docs/models/gradebook-audit-data-model.md`
- Modify: `.claude/rules/dbt-yaml.md`

- [ ] **Step 1: Audit the published data-model page**

`docs/models/gradebook-audit-data-model.md` is in the `mkdocs.yml` nav, so a
wrong claim there is a bug, not an expected stale spec. Its
`int_powerschool__gradebook_assignments_scores` sections are at lines 291 and
1031, with cross-references at 136, 370, 800, 808, 1087, 1099 and 1129.

The joins it describes do not change, and it never mentions `credit_type`; its
`region` mentions are all the grain of OTHER models, not a column of this one.
So the only thing that can be stale is a claim about which project the model
lives in. Read those sections and correct only that.

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores && \
grep -nE 'kipptaf|powerschool package|package' docs/models/gradebook-audit-data-model.md | \
  sed -n '1,40p'
```

If no section attributes the model to a project, make no edit and say so.

- [ ] **Step 2: Correct the stale classifier claim in the dbt YAML rule**

`.claude/rules/dbt-yaml.md` carries a claim that is wrong: with authorization in
the immediately-preceding turn, a `--target prod` build ran successfully during
the #5278 work. Replace this exact sentence:

```text
`--target prod` runs (`dbt build` / `run`) are blocked by the auto-mode
classifier as production deploys even with verbal approval — hand prod runs to
the user.
```

with:

```text
`--target prod` runs (`dbt build` / `run`) need direct user authorization in
the immediately-preceding turn, the same standard as
`stage_external_sources --target staging` below; without it, hand prod runs to
the user.
```

The source sentence is one wrapped line in the file, so match on a distinctive
fragment rather than the whole thing. Leave the neighbouring sentence about
`dbt compile` / `parse --target prod` NOT being blocked exactly as it is — this
plan's Task 3 relies on it and it is correct.

- [ ] **Step 3: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  .claude/rules/dbt-yaml.md docs/models/gradebook-audit-data-model.md </dev/null
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores add -u
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-gradebook-scores commit -m "docs: correct the prod-target claim in the dbt YAML rule

A --target prod build is not unconditionally classifier-blocked; it needs
direct user authorization in the immediately-preceding turn, the same
standard the file already applies to stage_external_sources.

Refs #5260

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

If Step 1 found nothing to correct, drop
`docs/models/gradebook-audit-data-model.md` from the lint list and the commit.
