# Focus Gradebook and Category Grades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put Miami AY2026 rows into `fct_grades_assignments` and
`fct_grades_category` by wiring Focus gradebook scores through 2 SIS-neutral
conformed models, without moving a single New Jersey row.

**Architecture:** Follow the `int_students__final_grades` precedent — do not
branch the `int_powerschool__*` models in place. Two new kipptaf models
(`int_students__gradebook_assignments_scores`, `int_students__category_grades`)
union the PowerSchool districts with a Focus branch, each year-scoped off a
`focus_academic_year_boundary` CTE so Miami's frozen AY2020-2025 archive stays
readable. The 2 facts repoint at those models.

**Tech Stack:** dbt (BigQuery), `uv run dbt`, `dbt_utils`. Design spec:
`docs/superpowers/specs/2026-08-28-focus-gradebook-category-facts-design.md`.

## Global Constraints

- **Worktree:**
  `/workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts`.
  Every `git` call uses `git -C <worktree>`; every dbt call uses
  `--project-dir <worktree>/src/dbt/<project>`. Never edit the main checkout.
- **Python:** always `uv run`. Never bare `python`, `dbt`, or `dagster`.
- **New Jersey output must not move.** Verify per model on `count(*)` plus
  `count(distinct format('%T|%T', ...))` on the key columns, for `kippnewark`,
  `kippcamden`, and `kipppaterson`.
- **One PR.** No package model gains or loses a column, so the #4290 deploy race
  cannot fire.
- **Do not add defensive dedupes** (`qualify row_number() = 1`,
  `dbt_utils.deduplicate()`, `select distinct`) anywhere in this plan. Where a
  join fans out, the fix is `not is_dropped_section`, never a dedupe. When a
  student leaves a section PowerSchool writes a second `stg_powerschool__cc` row
  with a negated `sectionid`; `cc_abs_sectionid` is the absolute value, so a
  join on it matches the dropped stint and the live one at once. Filtering the
  dropped stint is the correct fix; a dedupe would hide it. Residual overlap
  between two genuinely live stints is #3900, Ops cleanup #3915.
- **New Jersey output moves once, deliberately, in `fct_grades_category`.** That
  fact never filtered `is_dropped_section`, unlike `fct_grades_assignments`
  which always has, so it over-counts. Adding the filter drops Newark from
  677,721 to 674,261 and Camden from 244,410 to 242,070 for AY2026. Ratified
  2026-08-28 as a correction, not a regression. NJ output must not move anywhere
  else.
- **Year-scope every union** with
  `coalesce(min(academic_year), 9999) as min_academic_year` over
  `int_focus__schedule`. The bare `min()` returns NULL over an unbuilt `--defer`
  copy, `academic_year >= NULL` is NULL, and the `not (...)` filter would then
  drop every Miami archive row.
- **Focus timestamps are local-time day boundaries stored as UTC.** A due date
  reads `03:59:59Z`, which is `23:59:59` the _previous_ day in
  `America/New_York`. Always cast with
  `date(<ts>, '{{ var("local_timezone") }}')`. The focus package sets that var
  to `UTC`, so this cast belongs in kipptaf only.
- **Markdown/SQL lint:** do not run `trunk fmt` manually; the pre-commit hook
  formats. Before pushing, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree.
- **Commit messages** use conventional commits and end with the
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` trailer.

---

## File Structure

| File                                                                                                            | Responsibility                                                  |
| --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `src/dbt/focus/models/intermediate/properties/int_focus__gradebook_grades.yml`                                  | Correct the declared grain. Properties only — no SQL change.    |
| `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`                                                            | Declare 2 new Focus sources.                                    |
| `src/dbt/kipptaf/models/focus/intermediate/int_focus__gradebook_grades.sql` + `properties/`                     | Network-level passthrough wrapper.                              |
| `src/dbt/kipptaf/models/focus/staging/stg_focus__gradebook_assignments_join_course_periods.sql` + `properties/` | Passthrough wrapper supplying the `assignmentsectionid` analog. |
| `src/dbt/kipptaf/models/students/intermediate/int_students__gradebook_assignments_scores.sql` + `properties/`   | SIS-neutral assignment-score spine.                             |
| `src/dbt/kipptaf/models/students/intermediate/int_students__category_grades.sql` + `properties/`                | SIS-neutral category-grade spine.                               |
| `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql` + `properties/`                                 | Repoint source and enrollment join.                             |
| `src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql` + `properties/`                                    | Repoint source; drop its own enrollment join.                   |

---

## Task 1: Correct the grain declaration on `int_focus__gradebook_grades`

The model emits one row per score per resolved course period, but declares
`unique` on `student_gradebook_grade_id` alone. 91 ids currently appear twice —
a teacher posting one assignment across several of her course periods, with a
student scheduled into 2 of them. Focus's own ERD gives `gradebook_grades` as
student-by-assignment with no section FK, and Focus posts a report card grade in
both sections, so the rows are correct and the test is wrong.

**Files:**

- Modify:
  `src/dbt/focus/models/intermediate/properties/int_focus__gradebook_grades.yml`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `int_focus__gradebook_grades` with grain
  `(student_gradebook_grade_id, course_period_id)`. No column changes.

- [ ] **Step 1: Confirm the existing test fails against prod**

Run this against BigQuery:

```sql
select count(*) as duplicate_ids
from (
  select student_gradebook_grade_id
  from `teamster-332318.kippmiami_focus.int_focus__gradebook_grades`
  group by 1 having count(*) > 1
)
```

Expected: `91`. This is the failure the current `unique` test reports.

- [ ] **Step 2: Confirm the corrected grain holds**

```sql
select count(*) as n_rows,
  count(distinct format('%T|%T', student_gradebook_grade_id, course_period_id)) as n_grain
from `teamster-332318.kippmiami_focus.int_focus__gradebook_grades`
```

Expected: `n_rows` and `n_grain` both `4764` (the value grows daily; the two
numbers must be equal).

- [ ] **Step 3: Replace the test declaration**

In the `columns:` block, replace the `student_gradebook_grade_id` entry's tests.
Find:

```yaml
- name: student_gradebook_grade_id
  description: >-
    Primary key — Focus gradebook_grades id; one row per student per assignment.
  data_tests:
    - unique:
        config:
          severity: error
    - not_null:
        config:
          severity: error
```

Replace with:

```yaml
- name: student_gradebook_grade_id
  description: >-
    Focus gradebook_grades id. One row per student per assignment in the source;
    this model repeats it once per resolved course period, so it is unique only
    together with course_period_id.
  data_tests:
    - not_null:
        config:
          severity: error
```

- [ ] **Step 4: Add the model-level grain test**

Directly after the `description:` block and before `columns:`, add:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - student_gradebook_grade_id
          - course_period_id
```

- [ ] **Step 5: Correct the description**

Replace the sentences beginning "A grade resolves to one course period only"
through "Revisit if a graded row ever lands in two sections." with:

```text
      An assignment posted to several course periods produces one row per
      course period the student is scheduled into, so the grain is
      (student_gradebook_grade_id, course_period_id). That fan is correct, not a
      defect: Focus's schema stores a score against student and assignment with
      no section reference (vendor ERD, 2026-02-23), and Focus itself posts a
      report card grade in every section the student sits in, computed from the
      same scores. PowerSchool stores what Focus derives — its
      assignmentsectionid is already per section — so the fan is PowerSchool
      parity. Filtering the match by the assignment date against the schedule
      window was tested and rejected: it drops a legitimate grade for a student
      added to a section on 2026-08-18 and back-graded on work assigned
      2026-08-12, which is ordinary late-enrollment behavior.
```

- [ ] **Step 6: Build and test the model**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt build --select int_focus__gradebook_grades \
  --project-dir src/dbt/kippmiami
```

Expected: PASS on both `not_null` and `dbt_utils.unique_combination_of_columns`.
Run in the FOREGROUND.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  add src/dbt/focus/models/intermediate/properties/int_focus__gradebook_grades.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  commit -m "fix(dbt): correct int_focus__gradebook_grades grain to include course_period_id

Refs #5010

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Expose the 2 Focus models as kipptaf sources and wrappers

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__gradebook_grades.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__gradebook_grades.yml`
- Create:
  `src/dbt/kipptaf/models/focus/staging/stg_focus__gradebook_assignments_join_course_periods.sql`
- Create:
  `src/dbt/kipptaf/models/focus/staging/properties/stg_focus__gradebook_assignments_join_course_periods.yml`

**Interfaces:**

- Consumes: `int_focus__gradebook_grades` from Task 1.
- Produces: 2 kipptaf models, each `select *` plus `_dbt_source_project`. Task 3
  reads both. Key columns Task 3 relies on — from `int_focus__gradebook_grades`:
  `student_gradebook_grade_id`, `student_id`, `assignment_id`,
  `course_period_id`, `marking_period_id`, `points`, `assignment_points`,
  `due_date`, `assignment_title`, `assignment_type_title`, `late`,
  `exclude_from_average`, `assignment_exclude_from_average`. From
  `stg_focus__gradebook_assignments_join_course_periods`: `id`, `assignment_id`,
  `course_period_id`, `marking_period_id`.

- [ ] **Step 1: Add the source entries**

In `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`, append to the `tables:`
list:

```yaml
- name: int_focus__gradebook_grades
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__gradebook_grades
- name: stg_focus__gradebook_assignments_join_course_periods
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - stg_focus__gradebook_assignments_join_course_periods
```

- [ ] **Step 2: Create the intermediate wrapper**

`src/dbt/kipptaf/models/focus/intermediate/int_focus__gradebook_grades.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__gradebook_grades"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

- [ ] **Step 3: Create its properties file**

`src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__gradebook_grades.yml`:

```yaml
models:
  - name: int_focus__gradebook_grades
    description: >-
      Kipptaf-level union_relations passthrough of kippmiami's
      int_focus__gradebook_grades — Focus gradebook scores with the assignment,
      its category and category weight, and the resolved course period. One row
      per score per resolved course period. Read by
      int_students__gradebook_assignments_scores, which conforms these rows to
      the PowerSchool gradebook shape. Focus is Miami-only today; this shape
      lets a future region's Focus ingestion union in without a rewrite. Column
      docs/tests live on the kippmiami source model.
    config:
      meta:
        contains_pii: true
    columns:
      - name: _dbt_source_project
        description: District code location derived from _dbt_source_relation.
```

- [ ] **Step 4: Create the staging wrapper**

`src/dbt/kipptaf/models/focus/staging/stg_focus__gradebook_assignments_join_course_periods.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippmiami_focus",
                        "stg_focus__gradebook_assignments_join_course_periods",
                    )
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

- [ ] **Step 5: Create its properties file**

`src/dbt/kipptaf/models/focus/staging/properties/stg_focus__gradebook_assignments_join_course_periods.yml`:

```yaml
models:
  - name: stg_focus__gradebook_assignments_join_course_periods
    description: >-
      Kipptaf-level union_relations passthrough of kippmiami's
      stg_focus__gradebook_assignments_join_course_periods. One row per
      assignment per course period per marking period — the exact grain of
      PowerSchool's assignmentsectionid, which is why
      int_students__gradebook_assignments_scores uses this table's `id` as the
      Focus-side assignment-section identity. Column docs/tests live on the
      kippmiami source model.
    columns:
      - name: _dbt_source_project
        description: District code location derived from _dbt_source_relation.
```

- [ ] **Step 6: Build both wrappers**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt build \
  --select int_focus__gradebook_grades stg_focus__gradebook_assignments_join_course_periods \
  --project-dir src/dbt/kipptaf
```

Expected: 2 models PASS. Run in the FOREGROUND.

- [ ] **Step 7: Verify the wrappers carry the expected rows**

```sql
select
  (select count(*) from `teamster-332318.kipptaf_focus.int_focus__gradebook_grades`) as gg,
  (select count(*) from `teamster-332318.kipptaf_focus.stg_focus__gradebook_assignments_join_course_periods`) as ajcp
```

Expected: `gg` matches the kippmiami source count from Task 1 Step 2; `ajcp` is
in the hundreds of thousands.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts add \
  src/dbt/kipptaf/models/focus/sources-kippmiami.yml \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__gradebook_grades.sql \
  src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__gradebook_grades.yml \
  src/dbt/kipptaf/models/focus/staging/stg_focus__gradebook_assignments_join_course_periods.sql \
  src/dbt/kipptaf/models/focus/staging/properties/stg_focus__gradebook_assignments_join_course_periods.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  commit -m "feat(dbt): wrap Focus gradebook grades and assignment-course-period join in kipptaf

Refs #5010

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Build `int_students__gradebook_assignments_scores`

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__gradebook_assignments_scores.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__gradebook_assignments_scores.yml`

**Interfaces:**

- Consumes: the 2 wrappers from Task 2.
- Produces: `int_students__gradebook_assignments_scores` with exactly these 20
  columns — `_dbt_source_project` (string), `assignmentsectionid` (int64),
  `sectionsdcid` (int64), `students_dcid` (int64), `student_number` (int64),
  `academic_year` (int64), `marking_period_id` (int64), `duedate` (date),
  `assignment_name` (string), `category_name` (string), `category_code`
  (string), `points_earned` (float64), `numeric_grade_earned` (float64),
  `totalpointvalue` (float64), `assign_final_score_percent` (float64),
  `is_missing` (int64), `is_late` (int64), `is_exempt` (int64), `is_expected`
  (bool), `iscountedinfinalgrade` (int64). Task 4 reads `marking_period_id`,
  `category_code`, `points_earned`, `totalpointvalue`, `sectionsdcid`,
  `student_number`, `academic_year`, `_dbt_source_project`. Task 5 reads all of
  them.

- [ ] **Step 1: Write the model**

`src/dbt/kipptaf/models/students/intermediate/int_students__gradebook_assignments_scores.sql`:

```sql
with
    -- coalesce guards an empty int_focus__schedule (an unbuilt --defer dev
    -- copy): min() over no rows is NULL, `academic_year >= NULL` is NULL, so
    -- `not (...)` is NULL and the filter would drop every Miami archive row
    -- instead of keeping it. Same guard as int_students__course_enrollments.
    focus_academic_year_boundary as (
        select coalesce(min(academic_year), 9999) as min_academic_year,
        from {{ ref("int_focus__schedule") }}
    ),

    powerschool_conformed as (
        select
            asg._dbt_source_project,
            asg.assignmentsectionid,
            asg.sectionsdcid,
            asg.students_dcid,
            asg.student_number,
            asg.academic_year,
            asg.duedate,
            asg.assignment_name,
            asg.category_name,
            asg.category_code,
            asg.points_earned,
            asg.numeric_grade_earned,
            asg.totalpointvalue,
            asg.assign_final_score_percent,
            asg.is_missing,
            asg.is_late,
            asg.is_exempt,
            asg.is_expected,
            asg.iscountedinfinalgrade,

            -- PowerSchool dates assignments rather than storing them by term,
            -- so there is no marking period on a score. Carried as null so the
            -- Focus branch can supply one for int_students__category_grades.
            cast(null as int64) as marking_period_id,

        from {{ ref("int_powerschool__gradebook_assignments_scores") }} as asg
        cross join focus_academic_year_boundary as fay
        where
            not (
                asg._dbt_source_project = 'kippmiami'
                and asg.academic_year >= fay.min_academic_year
            )
    ),

    focus_conformed as (
        select
            gg._dbt_source_project,

            -- PowerSchool's assignmentsectionid is one row per assignment per
            -- section. Focus's exact analog is the assignment-to-course-period
            -- join row, whose id carries that same grain. Keeping the column
            -- name means fct_grades_assignments' surrogate key expression is
            -- untouched, so no NJ hash moves.
            ajcp.id as assignmentsectionid,

            gg.course_period_id as sectionsdcid,

            -- Focus's internal student row id, the students_dcid analog. Feeds
            -- grades_assignment_key only. The enrollment join in the fact uses
            -- student_number, which both branches carry.
            gg.student_id as students_dcid,

            st.student_number,

            mp.syear as academic_year,
            gg.marking_period_id,

            -- Focus stores day boundaries in local time as UTC: a due date
            -- lands at 03:59:59Z, which is 23:59:59 the PREVIOUS day in
            -- America/New_York. A bare date() shifts every due date forward one
            -- day, misfiling scores across quarter boundaries and against the
            -- enrollment window. The focus package cannot do this cast — its
            -- local_timezone var is UTC.
            date(gg.due_date, '{{ var("local_timezone") }}') as duedate,

            gg.assignment_title as assignment_name,
            gg.assignment_type_title as category_name,

            -- Focus's category titles share PowerSchool's storecode_type
            -- domain. An unmapped title falls through to itself, so a new Focus
            -- category surfaces in the fact rather than vanishing from it.
            case gg.assignment_type_title
                when 'Formative'
                then 'F'
                when 'Homework'
                then 'H'
                when 'Work Habits'
                then 'W'
                when 'Summative'
                then 'S'
                else gg.assignment_type_title
            end as category_code,

            -- points = -1 is Focus's not-yet-graded / excused sentinel, not a
            -- score. Left numeric it computes a score percent of -10 and
            -- poisons every category average that contains it.
            if(gg.points >= 0, cast(gg.points as float64), null) as points_earned,

            cast(gg.assignment_points as float64) as totalpointvalue,

            if(
                gg.points >= 0,
                round(
                    safe_divide(
                        cast(gg.points as float64),
                        cast(gg.assignment_points as float64)
                    )
                    * 100,
                    2
                ),
                null
            ) as assign_final_score_percent,

            -- Focus scores are points-based; there is no PERCENT / GRADESCALE
            -- score type carrying a numeric grade distinct from the points.
            cast(null as float64) as numeric_grade_earned,

            -- Focus records no missing flag on a gradebook score.
            cast(null as int64) as is_missing,

            if(gg.late, 1, 0) as is_late,
            if(gg.exclude_from_average, 1, 0) as is_exempt,
            if(gg.assignment_exclude_from_average, 0, 1) as iscountedinfinalgrade,

            not (
                gg.exclude_from_average or gg.assignment_exclude_from_average
            ) as is_expected,

        from {{ ref("int_focus__gradebook_grades") }} as gg
        -- inner, not left: a score with no course-period link cannot reach a
        -- section enrollment and so cannot reach either fact.
        inner join
            {{ ref("stg_focus__gradebook_assignments_join_course_periods") }} as ajcp
            on gg.assignment_id = ajcp.assignment_id
            and gg.course_period_id = ajcp.course_period_id
            and gg.marking_period_id = ajcp.marking_period_id
        inner join
            {{ ref("stg_focus__marking_periods") }} as mp
            on gg.marking_period_id = mp.marking_period_id
        inner join
            {{ ref("int_focus__students") }} as st on gg.student_id = st.student_id
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
```

- [ ] **Step 2: Build it**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt build --select int_students__gradebook_assignments_scores \
  --project-dir src/dbt/kipptaf
```

Expected: PASS. Run in the FOREGROUND.

- [ ] **Step 3: Verify NJ parity against prod**

```sql
select
  p._dbt_source_project,
  p.n_rows as prod_rows, n.n_rows as new_rows,
  p.n_key as prod_key, n.n_key as new_key,
from (
  select _dbt_source_project, count(*) as n_rows,
    count(distinct format('%T|%T', assignmentsectionid, students_dcid)) as n_key
  from `teamster-332318.kipptaf_powerschool.int_powerschool__gradebook_assignments_scores`
  where _dbt_source_project != 'kippmiami' group by 1
) as p
full join (
  select _dbt_source_project, count(*) as n_rows,
    count(distinct format('%T|%T', assignmentsectionid, students_dcid)) as n_key
  from `teamster-332318.kipptaf_students.int_students__gradebook_assignments_scores`
  where _dbt_source_project != 'kippmiami' group by 1
) as n using (_dbt_source_project)
order by 1
```

Expected: `prod_rows = new_rows` and `prod_key = new_key` on all 3 NJ regions.

- [ ] **Step 4: Verify Miami presence and the archive**

```sql
select
  countif(academic_year = 2026) as miami_ay2026,
  countif(academic_year between 2020 and 2025) as miami_archive,
  countif(academic_year = 2026 and points_earned < 0) as negative_scores,
  count(distinct format('%T|%T', assignmentsectionid, students_dcid)) as grain,
  count(*) as n_rows,
from `teamster-332318.kipptaf_students.int_students__gradebook_assignments_scores`
where _dbt_source_project = 'kippmiami'
```

Expected: `miami_ay2026` > 4,000 and rising; `miami_archive` matches prod's
`int_powerschool__gradebook_assignments_scores` Miami count for those years;
`negative_scores` = 0; `grain` = `n_rows`.

- [ ] **Step 5: Write the properties file**

Create
`src/dbt/kipptaf/models/students/intermediate/properties/int_students__gradebook_assignments_scores.yml`
with a `description` covering: the SIS-neutral purpose, the year-scope boundary,
that `assignmentsectionid` is Focus's assignment-to-course-period join id and
`students_dcid` is Focus's internal student id, the `-1` sentinel, the
local-timezone due-date cast, and which columns are null on the Focus branch
(`is_missing`, `numeric_grade_earned`, and `marking_period_id` on PowerScho­ol).
Add `config: materialized: table`, the grain test, and `contains_pii` on
`student_number` and `students_dcid`:

```yaml
config:
  materialized: table
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - assignmentsectionid
          - students_dcid
          - _dbt_source_project
```

- [ ] **Step 6: Rebuild with the tests**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt build --select int_students__gradebook_assignments_scores \
  --project-dir src/dbt/kipptaf
```

Expected: model and grain test PASS.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts add \
  src/dbt/kipptaf/models/students/intermediate/int_students__gradebook_assignments_scores.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__gradebook_assignments_scores.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  commit -m "feat(dbt): add SIS-neutral int_students__gradebook_assignments_scores

Refs #5010

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Build `int_students__category_grades`

The PowerSchool branch resolves `cc_dcid` with the join predicate lifted
verbatim from today's `fct_grades_category`, because
`int_powerschool__category_grades.sectionid` lives in a different id space from
`int_students__course_enrollments.sections_dcid` — 0 of 677,761 Newark rows
match the latter — and because that predicate carries a known fan-out that must
not move.

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__category_grades.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__category_grades.yml`

**Interfaces:**

- Consumes: `int_students__gradebook_assignments_scores` from Task 3.
- Produces: `int_students__category_grades` with exactly these 15 columns —
  `_dbt_source_project` (string), `cc_dcid` (int64), `region` (string),
  `schoolid` (int64), `yearid` (int64), `academic_year` (int64), `storecode`
  (string), `storecode_type` (string), `storecode_order` (string),
  `reporting_term` (string), `quarter` (string), `percent_grade` (float64),
  `citizenship_grade` (string), `percent_grade_y1_running` (float64),
  `is_current` (bool). Task 6 reads all of them.

- [ ] **Step 1: Write the model**

`src/dbt/kipptaf/models/students/intermediate/int_students__category_grades.sql`:

```sql
with
    focus_academic_year_boundary as (
        select coalesce(min(academic_year), 9999) as min_academic_year,
        from {{ ref("int_focus__schedule") }}
    ),

    course_enrollments as (
        select
            _dbt_source_project,
            cc_dcid,
            cc_studentid,
            cc_abs_sectionid,
            cc_yearid,
            cc_academic_year,
            cc_schoolid,
            sections_dcid,
            students_student_number,
            is_dropped_section,
            region,
        from {{ ref("int_students__course_enrollments") }}
    ),

    powerschool_conformed as (
        select
            cg._dbt_source_project,
            ce.cc_dcid,
            ce.region,
            cg.schoolid,
            cg.yearid,
            cg.academic_year,
            cg.storecode,
            cg.storecode_type,
            cg.storecode_order,
            cg.reporting_term,
            cg.quarter,
            cg.percent_grade,
            cg.citizenship_grade,
            cg.percent_grade_y1_running,
            cg.is_current,
        from {{ ref("int_powerschool__category_grades") }} as cg
        cross join focus_academic_year_boundary as fay
        -- not is_dropped_section is the correction this model makes.
        -- fct_grades_category never filtered it, so it over-counts: when a
        -- student leaves a section PowerSchool writes a second cc row with a
        -- negated sectionid, cc_abs_sectionid is the absolute value, and this
        -- join therefore matches the dropped stint alongside the live one.
        -- With the filter Camden is exactly 1:1 -- 242,070 category rows in,
        -- 242,070 out. fct_grades_assignments has always filtered it; this
        -- brings the two facts into line. Do NOT substitute a dedupe.
        inner join
            course_enrollments as ce
            on cg.studentid = ce.cc_studentid
            and cg.sectionid = ce.cc_abs_sectionid
            and cg.yearid = ce.cc_yearid
            and cg._dbt_source_project = ce._dbt_source_project
            and not ce.is_dropped_section
        where
            not (
                cg._dbt_source_project = 'kippmiami'
                and cg.academic_year >= fay.min_academic_year
            )
    ),

    -- Focus posts no category grade of its own -- there is no
    -- student_gradebook_category_grades table -- so the category percent is
    -- computed from the scores that make it up.
    focus_conformed as (
        select
            asg._dbt_source_project,
            ce.cc_dcid,
            ce.region,
            ce.cc_schoolid as schoolid,

            asg.academic_year,

            -- PowerSchool's yearid is academic_year - 1990. Deriving it keeps
            -- fct_grades_category's reporting-terms join working on both
            -- branches, matching int_students__final_grades.
            asg.academic_year - 1990 as yearid,

            asg.category_code as storecode_type,

            regexp_extract(mp.short_name, r'(\d+)$') as storecode_order,

            concat(
                asg.category_code, regexp_extract(mp.short_name, r'(\d+)$')
            ) as storecode,

            concat('RT', regexp_extract(mp.short_name, r'(\d+)$')) as reporting_term,

            mp.short_name as quarter,

            -- Weighted by points possible, and scored rows only: a not-yet-
            -- graded score (the -1 sentinel, already nulled upstream) must not
            -- drag the average toward zero.
            round(
                safe_divide(
                    sum(asg.points_earned),
                    sum(if(asg.points_earned is not null, asg.totalpointvalue, null))
                )
                * 100,
                2
            ) as percent_grade,

            -- Focus has no citizenship grade and no year-to-date rollup.
            cast(null as string) as citizenship_grade,
            cast(null as float64) as percent_grade_y1_running,

            current_date('{{ var("local_timezone") }}')
            between mp.start_date and mp.end_date as is_current,

        from {{ ref("int_students__gradebook_assignments_scores") }} as asg
        inner join
            {{ ref("stg_focus__marking_periods") }} as mp
            on asg.marking_period_id = mp.marking_period_id
        inner join
            course_enrollments as ce
            on asg.student_number = ce.students_student_number
            and asg.sectionsdcid = ce.sections_dcid
            and asg.academic_year = ce.cc_academic_year
            and asg._dbt_source_project = ce._dbt_source_project
            and not ce.is_dropped_section
        -- marking_period_id is null on every PowerSchool row, so the join above
        -- already restricts this branch to Focus. Stated explicitly so the
        -- scope survives a future PowerSchool marking-period backfill.
        where asg._dbt_source_project = 'kippmiami'
        group by
            asg._dbt_source_project,
            ce.cc_dcid,
            ce.region,
            ce.cc_schoolid,
            asg.academic_year,
            asg.category_code,
            mp.short_name,
            mp.start_date,
            mp.end_date
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
```

- [ ] **Step 2: Build it**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt build --select int_students__category_grades --project-dir src/dbt/kipptaf
```

Expected: PASS. Run in the FOREGROUND.

- [ ] **Step 3: Verify the intended NJ delta, and only that delta**

This model deliberately drops the phantom rows today's fact carries from
unfiltered dropped sections. Confirm the new count matches the _filtered_
baseline exactly, and that the difference from the unfiltered one is entirely
dropped-section rows:

```sql
select
  n._dbt_source_project,
  n.n_rows as new_rows,
  f.n_rows as expected_filtered,
  u.n_rows as old_unfiltered,
  u.n_rows - f.n_rows as phantom_rows_removed,
from (
  select _dbt_source_project, count(*) as n_rows
  from `teamster-332318.kipptaf_students.int_students__category_grades`
  where _dbt_source_project != 'kippmiami' and academic_year = 2026 group by 1
) as n
full join (
  select ce._dbt_source_project, count(*) as n_rows
  from `teamster-332318.kipptaf_powerschool.int_powerschool__category_grades` as cg
  inner join `teamster-332318.kipptaf_students.int_students__course_enrollments` as ce
    on cg.studentid = ce.cc_studentid and cg.sectionid = ce.cc_abs_sectionid
    and cg.yearid = ce.cc_yearid and cg._dbt_source_project = ce._dbt_source_project
    and not ce.is_dropped_section
  where ce._dbt_source_project != 'kippmiami' and cg.academic_year = 2026 group by 1
) as f using (_dbt_source_project)
full join (
  select ce._dbt_source_project, count(*) as n_rows
  from `teamster-332318.kipptaf_powerschool.int_powerschool__category_grades` as cg
  inner join `teamster-332318.kipptaf_students.int_students__course_enrollments` as ce
    on cg.studentid = ce.cc_studentid and cg.sectionid = ce.cc_abs_sectionid
    and cg.yearid = ce.cc_yearid and cg._dbt_source_project = ce._dbt_source_project
  where ce._dbt_source_project != 'kippmiami' and cg.academic_year = 2026 group by 1
) as u using (_dbt_source_project)
order by 1
```

Expected, measured 2026-08-28: `new_rows = expected_filtered` for every NJ
region. Camden `242070` (from `244410`, 2,340 removed) and Newark `674261` (from
`677721`, 3,460 removed). `new_rows` must never exceed `expected_filtered` —
that would mean the filter did not apply.

Camden's filtered count equals its category-grade row count exactly (242,070 in,
242,070 out), which is the proof the join is now 1:1. Newark's is 40 short of
its 674,301 category rows; those 40 match no live enrollment at all and are a
separate pre-existing gap, not something this change introduces.

- [ ] **Step 4: Verify Miami presence and grain**

```sql
select
  count(*) as n_rows,
  count(distinct format('%T|%T|%T|%T', cc_dcid, _dbt_source_project, storecode, storecode_type)) as grain,
  count(distinct storecode_type) as n_types,
  string_agg(distinct storecode_type order by storecode_type) as types,
  countif(percent_grade is null) as null_percent,
  min(percent_grade) as min_pct, max(percent_grade) as max_pct,
from `teamster-332318.kipptaf_students.int_students__category_grades`
where _dbt_source_project = 'kippmiami' and academic_year = 2026
```

Expected: `n_rows` equals `grain`; `types` is a subset of `F,H,S,W` with no `Q`;
`min_pct` >= 0 and `max_pct` <= 100 (a negative value means the `-1` sentinel
leaked).

- [ ] **Step 5: Write the properties file**

Create
`src/dbt/kipptaf/models/students/intermediate/properties/int_students__category_grades.yml`
documenting: the SIS-neutral purpose, that the Focus branch computes the
category percent because Focus posts none, that only `H`/`W`/`F`/`S` are emitted
and `Q` reaches the marts through `int_students__final_grades` /
`fct_grades_term`, the preserved PowerSchool fan-out with its `#3900` reference,
and that `citizenship_grade` / `percent_grade_y1_running` are null on Focus.
Add:

```yaml
config:
  materialized: table
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - cc_dcid
          - _dbt_source_project
          - storecode
          - storecode_type
```

- [ ] **Step 6: Rebuild with the tests**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt build --select int_students__category_grades --project-dir src/dbt/kipptaf
```

Expected: model and grain test PASS.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts add \
  src/dbt/kipptaf/models/students/intermediate/int_students__category_grades.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__category_grades.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  commit -m "feat(dbt): add SIS-neutral int_students__category_grades

Refs #5010

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Repoint `fct_grades_assignments`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml`

**Interfaces:**

- Consumes: `int_students__gradebook_assignments_scores` from Task 3.
- Produces: `fct_grades_assignments` with an unchanged column list and
  byte-identical NJ `grades_assignment_key` values.

- [ ] **Step 1: Capture the NJ baseline before editing**

```sql
select ce._dbt_source_project, count(*) as n_rows,
  count(distinct grades_assignment_key) as n_keys,
  min(grades_assignment_key) as min_key, max(grades_assignment_key) as max_key,
from `teamster-332318.kipptaf_marts.fct_grades_assignments` as f
inner join `teamster-332318.kipptaf_students.int_students__course_enrollments` as ce
  on f.student_section_enrollment_key = to_hex(md5(concat(
       coalesce(cast(ce.cc_dcid as string), ''), '-',
       coalesce(ce._dbt_source_project, ''))))
where ce._dbt_source_project != 'kippmiami'
group by 1 order by 1
```

Record all 4 values per region. Step 6 must reproduce them exactly.

- [ ] **Step 2: Swap the source and the CTE**

In `fct_grades_assignments.sql`, change the `course_enrollments` CTE's `ref`
from `base_powerschool__course_enrollments` to
`int_students__course_enrollments`, and drop `students_dcid` from its select
list (the fact now reads that column from the scores model). The CTE becomes:

```sql
    course_enrollments as (
        select
            _dbt_source_project,
            cc_academic_year,
            cc_schoolid,
            cc_dcid,
            cc_dateenrolled,
            cc_dateleft,
            sections_dcid,
            students_student_number,
            region,
        from {{ ref("int_students__course_enrollments") }}
        where not is_dropped_section
    ),
```

- [ ] **Step 3: Swap the model source**

Change:

```sql
from {{ ref("int_powerschool__gradebook_assignments_scores") }} as asg
```

to:

```sql
from {{ ref("int_students__gradebook_assignments_scores") }} as asg
```

- [ ] **Step 4: Fix the 2 joins**

Replace the `course_enrollments` join with:

```sql
inner join
    course_enrollments as ce
    on asg.sectionsdcid = ce.sections_dcid
    -- student_number, not students_dcid: students_dcid is null on every Miami
    -- row of int_students__course_enrollments. The swap is 1:1 inside every NJ
    -- district -- (sections_dcid, students_dcid) and (sections_dcid,
    -- students_student_number) yield identical distinct counts -- so no NJ row
    -- moves. The surrogate key still reads asg.students_dcid.
    and asg.student_number = ce.students_student_number
    and asg.duedate >= ce.cc_dateenrolled
    -- cc_dateleft is null on 18,582 of 19,398 Miami AY2026 course enrollments
    -- and on 0 NJ rows: `duedate < null` is null, which would drop nearly every
    -- Miami row. Miami-only in effect.
    and asg.duedate < coalesce(ce.cc_dateleft, date '9999-12-31')
    and asg._dbt_source_project = ce._dbt_source_project
```

Then replace the `student_enrollments` join with:

```sql
inner join
    student_enrollments as enr
    on ce.students_student_number = enr.student_number
    and ce.cc_schoolid = enr.schoolid
    -- academic_year on both sides. PowerSchool's yearid = academic_year - 1990
    -- has no Focus equivalent, and the swap is 1:1 for all 3 NJ regions.
    and ce.cc_academic_year = enr.academic_year
    and asg.duedate >= enr.entrydate
    and asg.duedate < enr.exitdate
    and ce._dbt_source_project = enr._dbt_source_project
```

- [ ] **Step 5: Update the `student_enrollments` CTE select list**

It currently selects `studentid` and `yearid`, which the join no longer uses.
Replace them with `academic_year`:

```sql
    student_enrollments as (
        select
            _dbt_source_project,
            schoolid,
            academic_year,
            student_number,
            entrydate,
            exitdate,
        from {{ ref("int_students__student_enrollment_union") }}
    ),
```

- [ ] **Step 6: Build and verify NJ is unmoved**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt build --select fct_grades_assignments --project-dir src/dbt/kipptaf
```

Then re-run the Step 1 query against the rebuilt model. Expected: `n_rows`,
`n_keys`, `min_key`, and `max_key` all identical to the recorded baseline for
all 3 NJ regions. A changed `min_key` or `max_key` means a hash input moved —
stop and diagnose before continuing.

- [ ] **Step 7: Verify Miami is present**

```sql
select count(*) as miami_ay2026
from `teamster-332318.kipptaf_marts.fct_grades_assignments` as f
inner join `teamster-332318.kipptaf_students.int_students__course_enrollments` as ce
  on f.student_section_enrollment_key = to_hex(md5(concat(
       coalesce(cast(ce.cc_dcid as string), ''), '-',
       coalesce(ce._dbt_source_project, ''))))
where ce._dbt_source_project = 'kippmiami' and f.academic_year = 2026
```

Expected: roughly 4,650 and rising daily. Zero means the enrollment window or
the join key is wrong.

- [ ] **Step 8: Update the model description**

In `properties/fct_grades_assignments.yml`, delete both paragraphs beginning
"PowerSchool only. Miami is absent from AY2026 forward" and "Miami's absence is
ratified as intentional on #4996", and replace with:

```text
      Sourced from int_students__gradebook_assignments_scores, which unions the
      PowerSchool districts with Miami's Focus gradebook. The Miami PowerSchool
      branch is scoped to years before Focus coverage begins and the Focus
      branch to years at or after it, so the frozen archive and the live SIS
      never overlap. Focus records no missing flag and no numeric grade distinct
      from the points score, so is_missing and numeric_grade_earned are null on
      every Miami AY2026 row.
```

- [ ] **Step 9: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts add \
  src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  commit -m "fix(dbt): source fct_grades_assignments from the SIS-neutral scores model

Refs #5010

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Repoint `fct_grades_category`

`int_students__category_grades` already resolved `cc_dcid` and `region`, so this
fact loses its own enrollment join entirely.

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_category.yml`

**Interfaces:**

- Consumes: `int_students__category_grades` from Task 4.
- Produces: `fct_grades_category` with an unchanged column list and
  byte-identical NJ `grades_category_key` values.

- [ ] **Step 1: Capture the NJ baseline**

```sql
select count(*) as n_rows, count(distinct grades_category_key) as n_keys,
  min(grades_category_key) as min_key, max(grades_category_key) as max_key,
from `teamster-332318.kipptaf_marts.fct_grades_category`
```

Record all 4 values. This fact carries no region column, so the check is
network-wide; Miami contributes 0 rows today, so any increase in Step 3 is
Miami's.

- [ ] **Step 2: Rewrite the model**

Replace the whole of `fct_grades_category.sql` with:

```sql
with
    reporting_terms as (
        select
            `type`,
            code,
            `name`,
            `start_date`,
            end_date,
            region,
            school_id,
            powerschool_year_id,
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'RT'
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "cg.cc_dcid",
                "cg._dbt_source_project",
                "cg.storecode",
                "cg.storecode_type",
            ]
        )
    }} as grades_category_key,

    {{ dbt_utils.generate_surrogate_key(["cg.cc_dcid", "cg._dbt_source_project"]) }}
    as student_section_enrollment_key,

    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,

    cg.academic_year,

    cg.storecode_type as `type`,
    cg.storecode_order as `order`,
    cg.reporting_term,
    cg.quarter,

    cg.percent_grade,
    cg.citizenship_grade,
    cg.percent_grade_y1_running as percent_grade_ytd_running,

    cg.is_current,
from {{ ref("int_students__category_grades") }} as cg
left join
    reporting_terms as rt
    on cg.storecode = rt.name
    and cg.schoolid = rt.school_id
    and cg.region = rt.region
    and cg.yearid = rt.powerschool_year_id
```

- [ ] **Step 3: Build and verify**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt build --select fct_grades_category --project-dir src/dbt/kipptaf
```

Then:

```sql
select count(*) as n_rows, count(distinct grades_category_key) as n_keys,
  min(grades_category_key) as min_key, max(grades_category_key) as max_key,
from `teamster-332318.kipptaf_marts.fct_grades_category`
```

Expected: `n_rows` equals the baseline, **minus** the phantom dropped-section
rows removed in Task 4 Step 3, **plus** the Miami AY2026 count from Task 4
Step 4. Compute the target before running and compare — a bare "it changed"
tells you nothing here, because this fact is expected to move in both directions
at once.

Every surviving NJ key must still be a key that existed before. Verify no NJ key
was invented:

```sql
select count(*) as nj_rows_unmatched
from `teamster-332318.kipptaf_marts.fct_grades_category` as f
inner join `teamster-332318.kipptaf_students.int_students__category_grades` as cg
  on f.grades_category_key = to_hex(md5(concat(
       coalesce(cast(cg.cc_dcid as string), ''), '-',
       coalesce(cg._dbt_source_project, ''), '-',
       coalesce(cg.storecode, ''), '-',
       coalesce(cg.storecode_type, ''))))
where cg._dbt_source_project != 'kippmiami' and f.grades_category_key is null
```

Expected: `0`.

- [ ] **Step 4: Update the model description**

In `properties/fct_grades_category.yml`, delete the paragraph beginning
"PowerSchool only. Miami is absent from AY2026 forward" and correct the grain
sentence. Replace "Categories are the grade reporting breakdowns within a term
(e.g., quarter grades vs exam grades)." with:

```text
      Categories are the gradebook categories within a term — storecode_type is
      Q for the quarter-overall grade and H, W, F, S for Homework, Work Habits,
      Formative and Summative. Sourced from int_students__category_grades, which
      unions the PowerSchool districts with a Focus branch computed from Miami's
      gradebook scores, since Focus posts no category grade of its own. The
      Focus branch emits H, W, F and S only; Miami's quarter-overall grade
      reaches the marts through fct_grades_term. citizenship_grade and
      percent_grade_ytd_running are null on every Miami row — Focus has neither.
```

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts add \
  src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql \
  src/dbt/kipptaf/models/marts/facts/properties/fct_grades_category.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  commit -m "fix(dbt): source fct_grades_category from the SIS-neutral category model

Refs #5010

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Add the Focus overlapping-course-period test

A student's course periods for one course, in one class period, must not overlap
by more than a shared boundary day — once resolved through the marking period.
That resolution is the whole trick: `int_focus__schedule.end_date` is null on
18,412 of 19,699 rows because the term boundary lives on the course period's
marking period. Without it the 188 semester-paired course periods read as
concurrent and the test is all false positives.

**Files:**

- Create:
  `src/dbt/focus/tests/int_focus__schedule__no_overlapping_course_periods.sql`
- Modify: `src/dbt/focus/tests/properties.yml`

**Interfaces:**

- Consumes: nothing from earlier tasks. Independent of Tasks 1 to 6.
- Produces: a singular data test. No model changes.

- [ ] **Step 1: Confirm the expected failure count**

```sql
with resolved as (
  select s.student_id, s.course_id, s.academic_year, s.course_period_id, s.period_id,
    coalesce(s.start_date, mp.start_date) as eff_start,
    coalesce(s.end_date, mp.end_date, date '9999-12-31') as eff_end,
  from `teamster-332318.kippmiami_focus.int_focus__schedule` as s
  left join `teamster-332318.kippmiami_focus.stg_focus__course_periods` as cp
    on s.course_period_id = cp.course_period_id
  left join `teamster-332318.kippmiami_focus.stg_focus__marking_periods` as mp
    on cp.marking_period_id = mp.marking_period_id
)
select count(*) as expected_failures
from resolved as a
inner join resolved as b
  on a.student_id = b.student_id and a.course_id = b.course_id
  and a.academic_year = b.academic_year and a.course_period_id < b.course_period_id
  and a.period_id = b.period_id
  and a.eff_start < b.eff_end and b.eff_start < a.eff_end
```

Expected: `2` as of 2026-08-28. Record the number you get — Step 4 must match
it.

- [ ] **Step 2: Write the test**

`src/dbt/focus/tests/int_focus__schedule__no_overlapping_course_periods.sql`:

```sql
-- A student must not sit in two course periods of the same course, in the same
-- class period, at the same time.
--
-- The marking-period resolution is load-bearing. int_focus__schedule.end_date
-- is null on 18,412 of 19,699 rows because Focus bounds a schedule row by its
-- course period's marking period rather than by the row's own end_date. Taken
-- literally, every Semester 1 row reads as open-ended and collides with its
-- Semester 2 partner -- 188 pairs that are simply a year-long course scheduled
-- as two halves. Falling back to the marking period's dates removes all of
-- them.
--
-- Scoped to a shared period_id. Two course periods of one course in DIFFERENT
-- class periods is a separate, much larger pattern (776 student-course groups
-- across 25 courses) that reads as a course meeting several times a week. It is
-- with Ops for a ruling and is deliberately not asserted here.
--
-- A single shared boundary day is a normal sequential transfer, so the
-- comparison is strict on both sides: only a genuine multi-day overlap is
-- returned. Any returned row is a failure.
with
    resolved as (
        select
            s.student_id,
            s.course_id,
            s.academic_year,
            s.course_period_id,
            s.period_id,
            coalesce(s.start_date, mp.start_date) as effective_start_date,
            coalesce(s.end_date, mp.end_date, date '9999-12-31') as effective_end_date,
        from {{ ref("int_focus__schedule") }} as s
        left join
            {{ ref("stg_focus__course_periods") }} as cp
            on s.course_period_id = cp.course_period_id
        left join
            {{ ref("stg_focus__marking_periods") }} as mp
            on cp.marking_period_id = mp.marking_period_id
    )

select
    a.student_id,
    a.course_id,
    a.academic_year,
    a.period_id,
    a.course_period_id as course_period_id_a,
    a.effective_start_date as effective_start_date_a,
    a.effective_end_date as effective_end_date_a,
    b.course_period_id as course_period_id_b,
    b.effective_start_date as effective_start_date_b,
    b.effective_end_date as effective_end_date_b,
from resolved as a
inner join
    resolved as b
    on a.student_id = b.student_id
    and a.course_id = b.course_id
    and a.academic_year = b.academic_year
    and a.period_id = b.period_id
    -- ordered pair: compares each combination once, never a row to itself
    and a.course_period_id < b.course_period_id
    and a.effective_start_date < b.effective_end_date
    and b.effective_start_date < a.effective_end_date
```

- [ ] **Step 3: Document it in the package test properties**

Append to `src/dbt/focus/tests/properties.yml` under `data_tests:`:

```yaml
- name: int_focus__schedule__no_overlapping_course_periods
  description: >-
    A student must not sit in two course periods of the same course, in the same
    class period, at overlapping times. Resolved through the marking period:
    int_focus__schedule.end_date is null on 18,412 of 19,699 rows because Focus
    bounds a schedule row by its course period's marking period, so a literal
    reading makes every Semester 1 row collide with its Semester 2 partner (188
    false pairs). Scoped to a shared period_id -- the same course in different
    class periods is a separate 776-group pattern with Ops for a ruling. Failing
    with 2 rows as of 2026-08-28, both the same student in two courses at
    period_id 2373, where the outgoing section runs 2026-08-12 to 2026-08-13
    while the incoming one starts 2026-08-12. Runs at the consuming district
    project's default warn severity. Any returned row is a failure.
  config:
    meta:
      dagster:
        ref:
          name: int_focus__schedule
          package: focus
```

- [ ] **Step 4: Run the test**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt test --select int_focus__schedule__no_overlapping_course_periods \
  --project-dir src/dbt/kippmiami
```

Expected: WARN with the row count from Step 1 (2). A PASS means the resolution
is wrong — probably the marking-period coalesce silently matched nothing. An
ERROR means severity did not inherit; check `kippmiami/dbt_project.yml` still
sets `+severity: warn`.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts add \
  src/dbt/focus/tests/int_focus__schedule__no_overlapping_course_periods.sql \
  src/dbt/focus/tests/properties.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  commit -m "test(dbt): assert no overlapping Focus course periods per course and class period

Refs #5010

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Move the PowerSchool overlap test into its package

The kipptaf copy reads `base_powerschool__course_enrollments`, which holds 0
Miami AY2026 rows, so it is structurally blind to the region this PR is about.
At package level each project holds one district, so the `_dbt_source_relation`
partition key drops.

**Files:**

- Delete:
  `src/dbt/kipptaf/tests/test_base_powerschool__course_enrollments_no_studyear_course_overlap.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml` (remove its entry)
- Create:
  `src/dbt/powerschool/tests/base_powerschool__course_enrollments__no_studyear_course_overlap.sql`
- Modify: `src/dbt/powerschool/tests/properties.yml`

**Interfaces:**

- Consumes: nothing from earlier tasks. Independent of Tasks 1 to 7.
- Produces: a singular data test in the powerschool package. No model changes.

- [ ] **Step 1: Record the current failure count**

```sql
with enrollments as (
  select _dbt_source_relation, cc_studyear, cc_course_number, cc_studentid,
    cc_dateenrolled, cc_dateleft,
    lag(cc_dateleft) over (
      partition by _dbt_source_relation, cc_studyear, cc_course_number
      order by cc_dateenrolled, cc_dateleft
    ) as prev_dateleft,
  from `teamster-332318.kipptaf_powerschool.base_powerschool__course_enrollments`
)
select regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as region, count(*) as failures
from enrollments where cc_dateenrolled < prev_dateleft group by 1 order by 1
```

Expected total: `15306` across all 4 regions as of 2026-08-28. Record the
per-region split — the sum of the per-district package runs must reproduce it.

- [ ] **Step 2: Create the package test**

`src/dbt/powerschool/tests/base_powerschool__course_enrollments__no_studyear_course_overlap.sql`:

```sql
-- Within a (student, year, course) -- cc_studyear is PowerSchool's composite
-- student-and-year identifier -- consecutive enrollment rows must not have date
-- ranges that overlap by more than one day. A single shared boundary day (one
-- row's cc_dateleft equal to the next row's cc_dateenrolled) is a normal
-- sequential transfer and is allowed; multi-day overlap is a source-side defect
-- that fans out date-range joins.
--
-- Lives in the package, not kipptaf: this asserts PowerSchool source quality,
-- and each district project holds one district, so no _dbt_source_relation
-- partition key is needed. The package's own base_powerschool__course_enrollments
-- already windows is_dropped_course on exactly (cc_studyear, cc_course_number).
--
-- Any returned row is a failure.
with
    enrollments as (
        select
            cc_studyear,
            cc_course_number,
            cc_studentid,
            cc_dateenrolled,
            cc_dateleft,

            lag(cc_dateleft) over (
                partition by cc_studyear, cc_course_number
                order by cc_dateenrolled, cc_dateleft
            ) as prev_dateleft,
        from {{ ref("base_powerschool__course_enrollments") }}
    )

select
    cc_studyear,
    cc_course_number,
    cc_studentid,
    cc_dateenrolled,
    cc_dateleft,
    prev_dateleft,
from enrollments
where cc_dateenrolled < prev_dateleft
```

- [ ] **Step 3: Document it in the package test properties**

Append to `src/dbt/powerschool/tests/properties.yml` under `data_tests:`:

```yaml
- name: base_powerschool__course_enrollments__no_studyear_course_overlap
  description: >-
    Within a (student, year, course) -- cc_studyear is PowerSchool's composite
    student-and-year identifier -- consecutive enrollment rows must not have
    date ranges that overlap by more than one day. A single shared boundary day
    is a normal sequential transfer and is allowed; multi-day overlap is the
    source-side defect behind the cc date-range fan-out (#3900, Ops cleanup
    #3915). Moved here from kipptaf, where it read the network-level union and
    was therefore blind to Miami, whose PowerSchool archive holds no AY2026
    rows. Failing with 15,306 rows network-wide as of 2026-08-28, across all 4
    districts. Runs at the consuming district project's default warn severity.
  config:
    meta:
      dagster:
        ref:
          name: base_powerschool__course_enrollments
          package: powerschool
```

- [ ] **Step 4: Delete the kipptaf copy**

```bash
rm /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts/src/dbt/kipptaf/tests/test_base_powerschool__course_enrollments_no_studyear_course_overlap.sql
```

Then remove its entry from `src/dbt/kipptaf/tests/properties.yml` — the block
starting at
`- name: test_base_powerschool__course_enrollments_no_studyear_course_overlap`
through the end of its `config:` block.

- [ ] **Step 5: Run the test in one district**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt test \
  --select base_powerschool__course_enrollments__no_studyear_course_overlap \
  --project-dir src/dbt/kippnewark
```

Expected: WARN with Newark's row count from Step 1. Repeat for `kippcamden` and
`kipppaterson`; the 3 counts plus Miami's must sum to the Step 1 total.

- [ ] **Step 6: Confirm kipptaf no longer references the deleted test**

```bash
grep -rn 'no_studyear_course_overlap' \
  /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts/src/dbt/kipptaf/
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts add \
  src/dbt/powerschool/tests/base_powerschool__course_enrollments__no_studyear_course_overlap.sql \
  src/dbt/powerschool/tests/properties.yml \
  src/dbt/kipptaf/tests/test_base_powerschool__course_enrollments_no_studyear_course_overlap.sql \
  src/dbt/kipptaf/tests/properties.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  commit -m "test(dbt): move the course-enrollment overlap test into the powerschool package

Refs #5010

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Seed CI, validate the whole graph, open the PR

**Files:**

- No model changes. Produces the PR.

**Interfaces:**

- Consumes: everything from Tasks 1 to 8.

- [ ] **Step 1: Seed the staged Focus copies for CI**

Authorized 2026-08-28. From the worktree:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt clone --target staging --state target/prod --project-dir src/dbt/kippmiami && \
  uv run dbt build --select int_focus__gradebook_grades --target staging \
  --project-dir src/dbt/kippmiami
```

The clone seeds `zz_stg_kippmiami_focus` from prod; the build refreshes
`int_focus__gradebook_grades` so CI exercises Task 1's corrected test.

- [ ] **Step 2: Build the full descendant graph empty**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt build --empty \
  --select int_students__gradebook_assignments_scores+ int_students__category_grades+ \
  --project-dir src/dbt/kipptaf
```

Expected: every model compiles. This proves column resolution across every
downstream consumer, not values.

- [ ] **Step 3: Confirm the FK tests pass**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  uv run dbt test --select fct_grades_assignments fct_grades_category \
  --project-dir src/dbt/kipptaf
```

Expected: `relationships` tests to `dim_student_section_enrollments` and
`dim_terms` PASS. All 19,398 Miami AY2026 course enrollments already resolve in
`dim_student_section_enrollments`, so an orphan means the `cc_dcid` mapping is
wrong.

- [ ] **Step 4: Lint every changed file**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts && \
  /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
    diff --name-only origin/main...HEAD | grep -v '^$') </dev/null
```

Background it if it runs over 2 minutes. Only interpret the output after the run
exits. Fix any `file:line` + rule findings; `unformatted file` findings are
handled by the pre-commit hook.

- [ ] **Step 5: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-gradebook-category-facts \
  push -u origin cbini/fix/claude-focus-gradebook-category-facts
```

- [ ] **Step 6: Open the PR**

Use `.github/pull_request_template.md` as the body. The body must state, per the
spec's validation split:

**Verified at full weight:** grain uniqueness on both conformed models and both
facts; 0-orphan FK joins; NJ parity as `count(*)` plus a distinct key count per
model per region; `grades_assignment_key` byte-identical for NJ; the Miami
AY2020-2025 archive unchanged.

**Directional until Q1 closes 2026-10-16:** every magnitude comparison of Miami
against NJ. Miami Q1 runs 2026-08-12 to 2026-10-16 and the gradebook holds about
2 weeks of a 9-week term, so scores per student and category-percent
distributions will move. These are not pass/fail criteria for this PR.

Include `Closes #5010`.

- [ ] **Step 7: After CI goes green, check the deploy**

Once merged and deployed, compare each rebuilt kipptaf wrapper's stored
`input_data_version` materialization tag against the upstream's current
`data_version` before trusting the green build. A mismatch is the #4290 race and
needs a manual `launch_run` of the wrapper plus every consumer.

- [ ] **Step 8: Pull CI warnings**

```text
mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)
```

Warnings unchanged from `main` are pre-existing — search open issues before
filing.

---

## Out of scope

- The gradebook-audit cluster. It keeps reading
  `int_powerschool__gradebook_assignments_scores` unchanged.
- `Q` rows on the Focus branch of `fct_grades_category`.
- `student_standard_grades`, still empty upstream.
- The `0`-prefixed duplicate Focus section set (283 groups, mostly KIPP Royalty
  Academy) — an Ops question, tracked separately.
- Porting the same-course overlap test to the focus and powerschool packages.
