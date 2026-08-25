# Focus Course Enrollments at kipptaf Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore Miami course-enrollment and section rows to the kipptaf
network layer for AY2026 by unioning Focus alongside PowerSchool in two new
SIS-neutral models.

**Architecture:** Move the union bodies out of kipptaf's
`base_powerschool__course_enrollments` and `base_powerschool__sections` into new
`int_students__course_enrollments` and `int_students__course_sections`, each
adding a Focus branch joined by BigQuery `full union all corresponding`. The two
`base_` models become one-line compatibility passthroughs so their 50-plus
consumers keep resolving. `dim_courses` gains the same treatment so Miami
sections resolve their course FK, and `dim_student_section_enrollments` repoints
to the new model and moves its student-stint join off PowerSchool internal ids.

**Tech Stack:** dbt (BigQuery), `uv` for all Python and dbt invocation, trunk
for lint, `dbt_utils` macros.

## Global Constraints

- Work in the worktree at
  `/workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments`.
  Every `git` call uses `git -C <worktree>`; every dbt call uses
  `--project-dir <worktree>/src/dbt/kipptaf`. Editing
  `/workspaces/teamster/<path>` instead silently dirties `main`.
- Always `uv run` — never bare `python`, `python3`, or `dbt`.
- Never run `trunk fmt` or `trunk check` casually; the pre-commit hook formats.
  Do run `trunk check --force --no-fix </dev/null` on changed `.sql` and `.yml`
  before pushing, from inside the worktree, using the absolute binary
  `/workspaces/teamster/.trunk/tools/trunk` (fall back to
  `~/.cache/trunk/launcher/trunk` if that symlink is absent).
- Focus data covers AY2026 only. The frozen `kippmiami_powerschool` archive
  holds Miami AY2020 through AY2025 and must keep serving those years. Derive
  the boundary with `select min(academic_year) from int_focus__schedule` — never
  hardcode `2026`.
- EVERY `dbt build` MUST carry
  `--defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  Without it the build reads empty personal-dev copies of the `int_focus__*`
  upstreams, silently drops the whole Focus branch, and still passes every test
  green. Plain `--defer` is not enough: it prefers an existing dev relation even
  when that relation is empty, so `--favor-state` is required. Verified on Task
  1 — the first build produced zero Miami AY2026 rows with no error.
- Columns Focus cannot source land `null`, never `false` and never a derived
  guess. The two drop flags carry a `TODO(#4968)` comment. `is_ap_course` does
  not: it is a New Jersey state crosswalk and Miami is Florida, so it is
  correctly absent rather than deferred.
- Backtick model and column names in every markdown file; trunk-fmt mangles bare
  `snake_case` as emphasis.
- Commit messages use conventional commits and end with
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

---

## Prerequisite — done

#4968 tracks the null `is_dropped_section` and `is_dropped_course` columns for
Miami, in the same shape #4927 uses for the six Miami attendance flags. Its
number is already written into the `TODO` comments below. No action needed
before Task 1.

---

### Task 1: `int_students__course_sections`

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__course_sections.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_sections.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/base/base_powerschool__sections.sql`

**Interfaces:**

- Consumes: `int_focus__course_periods`, `int_focus__courses`,
  `int_focus__schools`, `int_focus__users`, `int_focus__schedule`,
  `stg_google_sheets__people__locations`, `int_people__staff_roster`,
  `stg_powerschool__s_nj_crs_x`, and the four
  `source("<district>_powerschool", "base_powerschool__sections")` relations.
- Produces: a table at section grain keyed on
  `(sections_dcid, _dbt_source_project)`, carrying `sections_dcid`,
  `sections_id`, `sections_schoolid` (INT64), `sections_course_number` (STRING),
  `sections_section_number` (STRING), `courses_dcid` (INT64),
  `terms_academic_year` (INT64), `teachernumber` (STRING), `is_ap_course`
  (BOOL), `is_homeroom` (BOOL), `_dbt_source_project` (STRING). Task 2 depends
  on these names. `base_powerschool__sections` keeps its existing name and full
  column set as a passthrough, so its consumers need no edits.

- [ ] **Step 1: Write the model**

Create `int_students__course_sections.sql`. The `powerschool_conformed` CTE is
today's `base_powerschool__sections` body plus the year-scope filter and the new
`is_homeroom` column.

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "base_powerschool__sections"),
                    source("kippcamden_powerschool", "base_powerschool__sections"),
                    source("kippmiami_powerschool", "base_powerschool__sections"),
                    source("kipppaterson_powerschool", "base_powerschool__sections"),
                ]
            )
        }}
    ),

    sections as (
        select *, {{ extract_source_project() }} as _dbt_source_project,
        from union_relations
    ),

    -- Focus is Miami's system of record from AY2026 forward, but the frozen
    -- archive still holds Miami AY2020 through AY2025. Scope by year rather
    -- than excluding Miami wholesale, and derive the boundary so a Focus
    -- backfill of an earlier year does not silently double-count.
    powerschool_conformed as (
        select
            sec.*,

            if(cx.ap_course_subject is not null, true, false) as is_ap_course,

            coalesce(sec.sections_course_number like 'HR%', false) as is_homeroom,
        from sections as sec
        left join
            {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
            on sec.courses_dcid = cx.coursesdcid
            and sec._dbt_source_project = cx._dbt_source_project
        where
            not (
                sec._dbt_source_project = 'kippmiami'
                and sec.terms_academic_year
                >= (select min(academic_year) from {{ ref("int_focus__schedule") }})
            )
    ),

    focus_conformed as (
        select
            cp.course_period_id as sections_dcid,
            cp.course_period_id as sections_id,
            cp.course_id as courses_dcid,
            cp.syear as terms_academic_year,
            cp.short_name as sections_section_number,
            loc.powerschool_school_id as sections_schoolid,
            c.short_name as sections_course_number,
            sr.powerschool_teacher_number as teachernumber,

            'kippmiami' as _dbt_source_project,

            -- Focus carries a homeroom boolean on both the course and the
            -- course period and it is null on every row, so the homeroom
            -- course is identified by title. Same rule int_focus__advisory
            -- already uses. Elementary-only coverage is Focus configuration,
            -- tracked on #4868.
            coalesce(c.title like 'Homeroom%', false) as is_homeroom,

            -- The AP course subject crosswalk is a New Jersey state
            -- reporting table. Miami is Florida, so this is correctly absent
            -- rather than deferred -- no tracking issue.
            cast(null as bool) as is_ap_course,
        from {{ ref("int_focus__course_periods") }} as cp
        inner join {{ ref("int_focus__courses") }} as c on cp.course_id = c.course_id
        inner join {{ ref("int_focus__schools") }} as sch on cp.school_id = sch.id
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on sch.school_number = loc.focus_school_id
        left join {{ ref("int_focus__users") }} as usr on cp.teacher_id = usr.staff_id
        left join
            {{ ref("int_people__staff_roster") }} as sr
            on safe_cast(usr.ein as int64) = sr.employee_number
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
```

- [ ] **Step 2: Write the properties YAML**

Create `properties/int_students__course_sections.yml`. `materialized: table`
matches `int_students__student_enrollment_union` and keeps the `union_relations`
body off a view, which is what exposes a model to the #4290 stale-column race.

```yaml
models:
  - name: int_students__course_sections
    description: >-
      SIS-neutral course section spine. Each row is one section for one academic
      year. Unions the four PowerSchool district `base_powerschool__sections`
      sources with Miami's Focus course periods, conformed inline to the
      PowerSchool column vocabulary. The Miami PowerSchool branch is scoped to
      years before Focus coverage begins, so the frozen archive keeps serving
      Miami AY2020 through AY2025. Replaces `base_powerschool__sections` as the
      canonical section-grain source.
    config:
      materialized: table
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - sections_dcid
              - _dbt_source_project
    columns:
      - name: sections_dcid
        description: >-
          Section identifier. For Miami, the Focus `course_period_id`, which is
          the section analogue.
        data_type: int64
      - name: sections_schoolid
        description: >-
          Network school number. For Miami, resolved from Focus's internal
          school id through `int_focus__schools.school_number` and then the
          locations crosswalk. Focus's own `school_id` is a small internal
          integer, not the network identifier.
        data_type: int64
      - name: sections_course_number
        description: >-
          Course number. For Miami, the Focus course `short_name`, which holds
          the Florida state course code.
        data_type: string
      - name: teachernumber
        description: >-
          Lead teacher's PowerSchool teacher number. For Miami, resolved from
          the Focus `teacher_id` through `int_focus__users.ein` to the staff
          roster. All 77 current Miami Focus teachers resolve, because they
          predate the Focus migration; a Miami-only hire would not.
        data_type: string
      - name: is_homeroom
        description: >-
          Whether this section is a homeroom. Derived per branch: PowerSchool
          from the `HR%` course-number convention, Focus from a `Homeroom%`
          course title, because Focus's own homeroom boolean is null on every
          row. Focus coverage is elementary-only, tracked on #4868.
        data_type: bool
      - name: is_ap_course
        description: >-
          Whether this section is an AP course, from the New Jersey state course
          crosswalk. Null for Miami, which is Florida and has no such crosswalk.
        data_type: bool
      - name: terms_academic_year
        description: Academic year of the section.
        data_type: int64
      - name: _dbt_source_project
        description: >-
          Source-project discriminator (`kippnewark`, `kippcamden`, `kippmiami`,
          `kipppaterson`).
        data_type: string
```

- [ ] **Step 3: Convert `base_powerschool__sections` to a passthrough**

Replace the whole body. Match the wording of the existing
`base_powerschool__student_enrollments` passthrough.

```sql
-- Compatibility passthrough. The section logic moved to
-- int_students__course_sections, which carries both SIS branches; this model
-- exists so the consumers listed in #3999 keep resolving while they migrate.
-- Delete it once they have.
select *, from {{ ref("int_students__course_sections") }}
```

Do this in the same commit as the new model. Leaving the union body in both
models, even briefly, is duplicated logic.

- [ ] **Step 4: Build both models**

Run in the FOREGROUND — do not background it:

```bash
uv run dbt build --select int_students__course_sections base_powerschool__sections+1 \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments/src/dbt/kipptaf \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS, including the `unique_combination_of_columns` test.

- [ ] **Step 5: Confirm the column set did not narrow**

`base_powerschool__sections` consumers read columns the new model must still
produce. Compare against prod:

```sql
select column_name
from `teamster-332318.kipptaf_powerschool`.INFORMATION_SCHEMA.COLUMNS
where table_name = 'base_powerschool__sections'
except distinct
select column_name
from `teamster-332318.zz_cbini_kipptaf_powerschool`.INFORMATION_SCHEMA.COLUMNS
where table_name = 'base_powerschool__sections'
```

Expected: zero rows. Any row is a column a consumer reads that the new model
dropped.

- [ ] **Step 6: Verify both branches populated**

```sql
select _dbt_source_project, terms_academic_year, count(*) as n
from zz_cbini_kipptaf_students.int_students__course_sections
where terms_academic_year >= 2025
group by 1, 2
order by 1, 2
```

Expected: `kippmiami` present at `terms_academic_year = 2026` with roughly 5
schools' worth of course periods, AND still present at 2025 from the archive. If
Miami 2025 is missing, the year-scope filter is inverted.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/students/intermediate/int_students__course_sections.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_sections.yml \
  src/dbt/kipptaf/models/powerschool/base/base_powerschool__sections.sql </dev/null
```

```bash
wt=/workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments
git -C "$wt" add src/dbt/kipptaf/models/students/intermediate/int_students__course_sections.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_sections.yml \
  src/dbt/kipptaf/models/powerschool/base/base_powerschool__sections.sql
git -C "$wt" commit -m "feat(dbt): add int_students__course_sections with Focus branch"
```

---

### Task 2: `int_students__course_enrollments`

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__course_enrollments.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_enrollments.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/base/base_powerschool__course_enrollments.sql`

**Interfaces:**

- Consumes: everything Task 1 consumes, plus `int_focus__schedule`,
  `int_focus__students`,
  `stg_google_sheets__assessments__course_subject_crosswalk`, and the four
  `source("<district>_powerschool", "base_powerschool__course_enrollments")`
  relations.
- Produces: a table at course-enrollment grain keyed on
  `(cc_dcid, _dbt_source_project)`, carrying `cc_dcid` (INT64),
  `cc_academic_year` (INT64), `cc_dateenrolled` (DATE), `cc_dateleft` (DATE),
  `cc_course_number` (STRING), `sections_dcid` (INT64), `sections_schoolid`
  (INT64), `students_student_number` (INT64), `teachernumber` (STRING),
  `is_dropped_section` (BOOL), `is_dropped_course` (BOOL), `is_homeroom` (BOOL),
  `region` (STRING), `_dbt_source_project` (STRING). Task 3 depends on these
  names. `base_powerschool__course_enrollments` keeps its existing name and full
  column set as a passthrough, so its 50-plus consumers need no edits.

- [ ] **Step 1: Write the model**

The `powerschool_conformed` CTE is today's kipptaf
`base_powerschool__course_enrollments` body, moved verbatim, plus the year-scope
filter and `is_homeroom`. Copy the existing body rather than retyping it — it
carries a long `courses_credittype` case statement and a
`rn_student_year_illuminate_subject_desc` window that must not change.

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                ]
            )
        }}
    ),

    add_dbt_field as (
        select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,
        from union_relations
        -- see int_students__course_sections for why this is year-scoped
        where
            not (
                {{ extract_source_project("ur") }} = 'kippmiami'
                and ur.cc_academic_year
                >= (select min(academic_year) from {{ ref("int_focus__schedule") }})
            )
    ),

    powerschool_conformed as (
        -- EXISTING BODY of kipptaf base_powerschool__course_enrollments,
        -- unchanged, reading `add_dbt_field as a`, with one column appended:
        --     coalesce(a.cc_course_number like 'HR%', false) as is_homeroom,
        ...
    ),

    focus_conformed as (
        select
            s.student_schedule_id as cc_dcid,
            s.academic_year as cc_academic_year,
            s.course_period_id as sections_dcid,
            s.course_period_id as cc_sectionid,
            s.start_date as cc_dateenrolled,
            s.end_date as cc_dateleft,
            st.student_number as students_student_number,
            loc.powerschool_school_id as sections_schoolid,
            loc.powerschool_school_id as cc_schoolid,
            c.short_name as cc_course_number,
            sr.powerschool_teacher_number as teachernumber,

            'kippmiami' as _dbt_source_project,
            'Miami' as region,

            -- Focus's homeroom boolean is null on every row; identified by
            -- title instead, matching int_focus__advisory. See #4868.
            coalesce(s.course_title like 'Homeroom%', false) as is_homeroom,

            -- TODO(#4968): PowerSchool derives both flags from its
            -- `sectionid < 0` convention. Focus has no drop convention at all,
            -- so these are null rather than false: Miami is excluded from
            -- network drop-rate metrics instead of diluting them.
            cast(null as bool) as is_dropped_section,
            cast(null as bool) as is_dropped_course,

            -- New Jersey state reporting crosswalk; Miami is Florida, so
            -- correctly absent rather than deferred.
            cast(null as bool) as is_ap_course,
        from {{ ref("int_focus__schedule") }} as s
        inner join {{ ref("int_focus__students") }} as st on s.student_id = st.student_id
        inner join {{ ref("int_focus__courses") }} as c on s.course_id = c.course_id
        inner join {{ ref("int_focus__schools") }} as sch on s.schoolid = sch.id
        left join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on sch.school_number = loc.focus_school_id
        left join {{ ref("int_focus__users") }} as usr on s.teacher_id = usr.staff_id
        left join
            {{ ref("int_people__staff_roster") }} as sr
            on safe_cast(usr.ein as int64) = sr.employee_number
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
```

- [ ] **Step 2: Write the properties YAML**

Mirror Task 1's YAML. `materialized: table`. Required tests:

```yaml
models:
  - name: int_students__course_enrollments
    description: >-
      SIS-neutral course enrollment spine. Each row is one student's enrolment
      in one section. Unions the four PowerSchool district
      `base_powerschool__course_enrollments` sources with Miami's Focus
      schedule, conformed inline to the PowerSchool column vocabulary. The Miami
      PowerSchool branch is scoped to years before Focus coverage begins.
      Replaces `base_powerschool__course_enrollments` as the canonical
      course-enrollment-grain source.
    config:
      materialized: table
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - cc_dcid
              - _dbt_source_project
    columns:
      - name: cc_dcid
        description: >-
          Course enrollment identifier. For Miami, the Focus
          `student_schedule_id`, unique across all 19,594 Focus schedule rows.
        data_type: int64
      - name: is_dropped_section
        description: >-
          Whether the student dropped this section. PowerSchool derives it from
          its `sectionid < 0` convention. Null for Miami: Focus has no drop
          convention, and a false here would put 19,594 guaranteed-not-dropped
          rows into every network drop-rate metric.
        data_type: bool
      - name: is_dropped_course
        description: >-
          Whether every section of this course was dropped. Null for Miami, for
          the same reason as `is_dropped_section`.
        data_type: bool
      - name: is_homeroom
        description: >-
          Whether this enrollment is a homeroom. PowerSchool from the `HR%`
          course-number convention, Focus from a `Homeroom%` course title. Focus
          coverage is elementary-only, tracked on #4868.
        data_type: bool
      - name: students_student_number
        description: >-
          Canonical network student number. For Miami, from
          `int_focus__students.student_number`, which already has the 8400
          Miami-Dade district prefix stripped.
        data_type: int64
```

- [ ] **Step 3: Convert `base_powerschool__course_enrollments` to a
      passthrough**

Replace the whole body.

```sql
-- Compatibility passthrough. The course enrollment logic moved to
-- int_students__course_enrollments, which carries both SIS branches; this
-- model exists so the consumers listed in #3999 keep resolving while they
-- migrate. Delete it once they have.
select *, from {{ ref("int_students__course_enrollments") }}
```

Do this in the same commit as the new model. Leaving the union body in both
models, even briefly, is duplicated logic.

- [ ] **Step 4: Build both models**

FOREGROUND only:

```bash
uv run dbt build --select int_students__course_enrollments base_powerschool__course_enrollments+1 \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments/src/dbt/kipptaf \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS.

- [ ] **Step 5: Confirm the column set did not narrow**

This model has more than 50 consumers, so a dropped column is the highest-risk
failure in the whole plan.

```sql
select column_name
from `teamster-332318.kipptaf_powerschool`.INFORMATION_SCHEMA.COLUMNS
where table_name = 'base_powerschool__course_enrollments'
except distinct
select column_name
from `teamster-332318.zz_cbini_kipptaf_powerschool`.INFORMATION_SCHEMA.COLUMNS
where table_name = 'base_powerschool__course_enrollments'
```

Expected: zero rows.

- [ ] **Step 6: Verify NJ parity and Miami presence**

```sql
select _dbt_source_project, cc_academic_year, count(*) as n
from zz_cbini_kipptaf_students.int_students__course_enrollments
where cc_academic_year >= 2025
group by 1, 2
order by 1, 2
```

Expected, against the measurements in the spec:

| `_dbt_source_project` | 2025   | 2026           |
| --------------------- | ------ | -------------- |
| `kippnewark`          | 51,575 | 44,481         |
| `kippcamden`          | 18,730 | 14,655         |
| `kipppaterson`        | 4,531  | 3,947          |
| `kippmiami`           | 17,065 | roughly 19,594 |

NJ figures must match exactly. A changed NJ number means the year-scope filter
leaked past Miami.

- [ ] **Step 7: Lint and commit**

Same trunk check as Task 1 Step 7, with this task's three paths.

```bash
wt=/workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments
git -C "$wt" add src/dbt/kipptaf/models/students/intermediate/int_students__course_enrollments.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__course_enrollments.yml \
  src/dbt/kipptaf/models/powerschool/base/base_powerschool__course_enrollments.sql
git -C "$wt" commit -m "feat(dbt): add int_students__course_enrollments with Focus branch"
```

---

### Task 3: Branch `dim_courses` so Miami sections resolve their course FK

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__courses.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__courses.yml`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql`

**Interfaces:**

- Consumes: `stg_powerschool__courses`, `int_focus__courses`,
  `stg_google_sheets__assessments__course_subject_crosswalk`.
- Produces: one row per `(course_number, _dbt_source_project)`. `dim_courses`
  keeps its existing output columns and its unique `course_key`.

**Why this task exists.** Task 1 puts Miami Focus sections into
`dim_course_sections`, whose `course_key` is
`surrogate_key(sections_course_number, _dbt_source_project)`. `dim_courses`
reads `stg_powerschool__courses`, a pure PowerSchool model, so every Miami
section's `course_key` points at a row that does not exist — 844 orphans on the
warn-severity relationships test after Task 1.

Task 1 set the Focus `sections_course_number` to
`int_focus__courses.short_name`. This model MUST key on exactly that column, or
the FK stays broken.

- [ ] **Step 1: Write `int_students__courses`**

```sql
with
    powerschool_conformed as (
        select
            course_number,
            course_name,
            credittype,
            credit_hours,
            _dbt_source_project,
        from {{ ref("stg_powerschool__courses") }}
    ),

    -- int_focus__courses carries one row per course per school year: 14,616
    -- rows against 1,350 distinct short_name. dim_courses.course_key is unique
    -- on (course_number, _dbt_source_project), so the Focus branch keeps the
    -- most recent year per short_name. The 3 courses with a null short_name
    -- cannot produce a key and are dropped -- no scheduled course period
    -- references one, verified 2026-08-25.
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    focus_courses as (
        select
            syear,
            short_name as course_number,
            title as course_name,
            credit_hours,

            -- Focus has no credit-type field. Null rather than a guess.
            cast(null as string) as credittype,

            'kippmiami' as _dbt_source_project,
        from {{ ref("int_focus__courses") }}
        where short_name is not null
    ),

    focus_deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="focus_courses",
                partition_by="course_number",
                order_by="syear desc",
            )
        }}
    ),

    focus_conformed as (
        select * except (syear),
        from focus_deduplicated
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
```

Do NOT reach for `select distinct` or `qualify row_number() = 1` here. This repo
uses `dbt_utils.deduplicate`.

- [ ] **Step 2: Write the properties YAML**

```yaml
models:
  - name: int_students__courses
    description: >-
      SIS-neutral course spine. One row per course per source project. Unions
      `stg_powerschool__courses` with Miami's Focus courses, conformed to the
      PowerSchool column vocabulary and deduplicated to the most recent school
      year per course number. Exists so `dim_courses` can resolve the course FK
      for Miami sections.
    config:
      materialized: table
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - course_number
              - _dbt_source_project
    columns:
      - name: course_number
        description: >-
          Course number. For Miami, the Focus course `short_name`, which holds
          the Florida state course code. This must match the
          `sections_course_number` that `int_students__course_sections` writes
          for Focus, because `dim_course_sections.course_key` is derived from
          it.
        data_type: string
      - name: credittype
        description: >-
          Credit type. Null for Miami: Focus has no equivalent field.
        data_type: string
      - name: _dbt_source_project
        description: >-
          Source-project discriminator (`kippnewark`, `kippcamden`, `kippmiami`,
          `kipppaterson`).
        data_type: string
```

- [ ] **Step 3: Repoint `dim_courses`**

Change the one ref. Everything else in the file stays.

```sql
from {{ ref("int_students__courses") }} as c
```

The `stg_google_sheets__assessments__course_subject_crosswalk` join beside it
keys on `powerschool_course_number`, so Miami rows get a null `academic_subject`
and `is_foundations`. That is correct — the crosswalk is a PowerSchool artifact
— and needs no branch.

- [ ] **Step 4: Build and verify the orphans are gone**

FOREGROUND only:

```bash
uv run dbt build --select int_students__courses dim_courses dim_course_sections \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments/src/dbt/kipptaf \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS, and the `relationships` test from
`dim_course_sections.course_key` to `dim_courses.course_key` reports **0
failures**. It reported 844 after Task 1. A non-zero count means `course_number`
here does not match the `sections_course_number` Task 1 wrote.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/students/intermediate/int_students__courses.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__courses.yml \
  src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql </dev/null
```

```bash
wt=/workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments
git -C "$wt" add src/dbt/kipptaf/models/students/intermediate/int_students__courses.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__courses.yml \
  src/dbt/kipptaf/models/marts/dimensions/dim_courses.sql
git -C "$wt" commit -m "fix(dbt): branch dim_courses so Miami sections resolve their course FK"
```

---

### Task 4: Repoint `dim_student_section_enrollments`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`

**Interfaces:**

- Consumes: `int_students__course_enrollments` (Task 2),
  `int_students__student_enrollment_union` (existing).
- Produces: unchanged output columns. Only the source ref, the join key, and the
  `is_homeroom` derivation change.

- [ ] **Step 1: Change the ref**

In the `enrollment_overlap` CTE, replace
`{{ ref("base_powerschool__course_enrollments") }}` with
`{{ ref("int_students__course_enrollments") }}`.

- [ ] **Step 2: Move the stint join to the neutral key**

Replace the three PowerSchool-internal join predicates. The date-overlap
predicates below them are unchanged.

```sql
        left join
            student_enrollments as enr
            on cc.students_student_number = enr.student_number
            and cc.sections_schoolid = enr.schoolid
            and cc.cc_academic_year = enr.academic_year
            and cc._dbt_source_project = enr._dbt_source_project
            and cc.cc_dateleft > enr.entrydate
            and cc.cc_dateenrolled < enr.exitdate
```

The `student_enrollments` CTE at the top of the file must select
`student_number` and `academic_year`; it already does. Remove `studentid` and
`yearid` from that CTE's select list, since nothing reads them after this
change.

- [ ] **Step 3: Read `is_homeroom` instead of deriving it**

In the `section_enrollments` CTE, replace

```sql
            coalesce(cc_course_number like 'HR%', false) as is_homeroom,
```

with a passthrough of the upstream column, and add `is_homeroom` to the
`enrollment_overlap` CTE's select list so it survives the dedupe. The `HR%` rule
is a PowerSchool course-number convention that Focus course numbers do not
follow, which is why it moved upstream.

- [ ] **Step 4: Build and verify no Miami orphans**

FOREGROUND only:

```bash
uv run dbt build --select dim_student_section_enrollments \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments/src/dbt/kipptaf \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Then the check this whole task exists for:

```sql
select
  count(*) as miami_2026_rows,
  countif(student_enrollment_key is null) as orphaned,
  countif(is_homeroom) as homeroom_rows
from zz_cbini_kipptaf_marts.dim_student_section_enrollments as d
inner join zz_cbini_kipptaf_students.int_students__course_enrollments as cc
  on d.student_section_enrollment_key
     = {{ dbt_utils.generate_surrogate_key(["cc.cc_dcid", "cc._dbt_source_project"]) }}
where cc._dbt_source_project = 'kippmiami' and d.academic_year = 2026
```

Expected: `miami_2026_rows` well above zero, `orphaned` = 0. A non-zero
`orphaned` means the neutral join key is still not matching, and the task is not
done.

- [ ] **Step 5: Lint and commit**

```bash
git -C "$wt" commit -m "fix(dbt): join section enrollments to stints on the neutral key"
```

---

### Task 5: Whole-branch validation

**Files:**

- Create:
  `src/dbt/kipptaf/tests/test_focus_course_sections_teacher_resolves.sql`

**Interfaces:**

- Consumes: every model from Tasks 1 through 4.
- Produces: no model. A warn-severity test plus recorded validation evidence.

- [ ] **Step 1: Write the warn-severity teacher test**

All 77 current Miami Focus teachers resolve because they predate the Focus
migration. A Miami-only hire would not, and that should warn rather than break
the build.

```sql
{{ config(severity="warn") }}

-- Every Focus section should resolve a lead teacher through the staff roster.
-- All 77 current Miami teachers do, because they predate the Focus migration
-- and still carry a PowerSchool teacher number. A Miami-only hire would not,
-- so this warns rather than errors -- it is an Ops correction in the roster,
-- not a modeling defect.
select sections_dcid, _dbt_source_project,
from {{ ref("int_students__course_sections") }}
where _dbt_source_project = 'kippmiami' and teachernumber is null
```

- [ ] **Step 2: Record NJ parity against prod**

Run this for `int_students__course_enrollments` as written, then again
substituting `int_students__course_sections` (key columns `sections_dcid`,
`_dbt_source_project`) and `dim_student_section_enrollments` (key column
`student_section_enrollment_key`, in `zz_cbini_kipptaf_marts`), comparing each
dev build to its prod counterpart for the three NJ regions:

```sql
select
  count(*) as rows_n,
  count(distinct format('%T|%T', cc_dcid, _dbt_source_project)) as distinct_key
from `teamster-332318.zz_cbini_kipptaf_students.int_students__course_enrollments`
where _dbt_source_project != 'kippmiami'
```

Expected: identical between dev and `kipptaf_students` / `kipptaf_marts` prod.
Any drift is a regression introduced by the year-scope filter or the join-key
change, not an improvement.

- [ ] **Step 3: Confirm Miami history survived**

```sql
select cc_academic_year, count(*) as n
from zz_cbini_kipptaf_students.int_students__course_enrollments
where _dbt_source_project = 'kippmiami' and cc_academic_year between 2020 and 2025
group by 1
order by 1
```

Expected: matches the archive for all six years, AY2025 at 17,065. Missing years
mean the year-scope filter deleted history.

- [ ] **Step 4: Run the descendant graph empty**

Run this AFTER Steps 2 and 3 — `--empty` rebuilds every selected relation as
`limit 0`, so a validation query run afterwards reads zero rows and looks like
catastrophic loss.

```bash
uv run dbt build --empty --select int_students__course_enrollments+ int_students__course_sections+ \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments/src/dbt/kipptaf \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS. This proves column resolution across every descendant, which is
what catches a consumer reading a column the passthrough no longer carries.

- [ ] **Step 5: Rebuild without `--empty`, lint, commit, push**

```bash
uv run dbt build --select int_students__course_enrollments+ int_students__course_sections+ \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-course-enrollments/src/dbt/kipptaf \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Lint every changed `.sql` and `.yml` with `trunk check --force`, then:

```bash
git -C "$wt" commit -m "test(dbt): add warn test for unresolved Focus section teachers"
git -C "$wt" push -u origin cbini/fix/claude-focus-course-enrollments
```

Open the PR with `.github/pull_request_template.md` as the body, and
`Refs #4925` plus the prerequisite issue reference.

---

## Notes for the reviewer

- This PR does not touch any focus-package model's columns, so it needs no
  `zz_stg_kippmiami_focus` staging seed and has no cross-project CI
  coordination. That is why the issue sequences it first.
- Moving the `union_relations` body off a view is a side benefit worth keeping:
  `base_powerschool__course_enrollments` is currently a view containing
  `union_relations`, which the Dagster translator assigns
  `dbt_union_relations_automation_condition()` — the exact #4290 stale-column
  exposure. As a table-materialized `int_students__` model it gets the eager
  table condition instead.
- `base_powerschool__sections` is already a table (32,802 rows); its passthrough
  becomes a view. That is the intended direction.
