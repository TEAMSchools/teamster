# PowerSchool Package Identity, PR A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the shared `powerschool` package's GPA, final grades, calendar
day, and student enrollment models the student identity and school columns that
kipptaf joins for today, and re-include the package in kippmiami so one prod
build lands those columns in the Miami archive.

**Architecture:** Five package models change in `src/dbt/powerschool`: 3 GPA
intermediates and the new `int_powerschool__calendar_day` gain left joins to
`stg_powerschool__students` and `stg_powerschool__schools`; 2 base models pass
columns through from joins they already make. `src/dbt/kippmiami` re-includes
the package with the 16 archive hooks from #5201 and #5224, unchanged. kipptaf
is untouched; PR B (spec section "kipptaf changes") reads the new columns after
the user rebuilds the archive in prod.

**Tech Stack:** dbt (BigQuery), `uv run dbt`, dbt unit tests, trunk.

Spec:
`docs/superpowers/specs/2026-09-09-powerschool-package-identity-design.md`.
Issue: #5228.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity`.
  Every file path is under it. Every git call is
  `git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity`.
  Below, `$WT` in prose means that path; type it out in commands, never as a
  shell variable (uppercase variables are hook-blocked).
- Never run bare `dbt`; always
  `uv run dbt ... --project-dir <abs worktree path>/src/dbt/<project>`. From a
  worktree, `--state` must be the absolute main-checkout path
  `/workspaces/teamster/src/dbt/<project>/target/prod`.
- New identity columns are named `students_dcid` and `students_student_number`.
  New school columns are named `school_name`, `school_abbreviation`,
  `school_level`. No other student or school columns.
- Every new join in a GPA model is a `left join`, so row counts stay identical
  to prod. The parity checks below depend on that.
- `students_student_number` is PII. Tag it `config.meta.contains_pii: true` in
  the package YAML, under the column, in the shape
  `stg_powerschool__students.yml` uses. Never paste student rows into a commit,
  PR, or issue; counts only.
- dbt unit tests need every `ref()` the model uses listed under `given`, or the
  test fails to compile with "node not found". A new join means a new `given`
  entry, empty rows are fine.
- Package staging models are contract-enforced; base and intermediate are not.
  Still list every new column in the model's properties file with `data_type`.
- YAML snippets in this plan are shown unindented by the formatter. Indent each
  pasted block to match the surrounding `columns:` or `given:` list.
- Before pushing, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- Do not write the bare token `env` in any commit message, PR body, or issue
  text; write "environment".
- Commit messages end with `Refs #5228` and the co-author line
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Write the message
  to `/workspaces/teamster/.claude/scratch/commit-msg.txt` and commit with `-F`,
  so the hook never scans a `-m` string.

## File structure

Package, `src/dbt/powerschool/models/sis/`:

- `base/base_powerschool__final_grades.sql` and
  `base/properties/base_powerschool__final_grades.yml`: passthrough of 4 columns
  from course enrollments.
- `base/base_powerschool__student_enrollments.sql` and
  `base/properties/base_powerschool__student_enrollments.yml`: one new column
  from a second schools join.
- `intermediate/int_powerschool__gpa_term.sql`,
  `intermediate/int_powerschool__gpa_cumulative.sql`,
  `intermediate/int_powerschool__gpa_cumulative_year.sql` and their
  `intermediate/properties/*.yml`: identity and school joins on the final
  select, YAML columns, PII tag, unit test inputs.
- `intermediate/int_powerschool__calendar_day.sql` and
  `intermediate/properties/int_powerschool__calendar_day.yml`: new model.

kippmiami, `src/dbt/kippmiami/`:

- `packages.yml`: add the package.
- `dbt_project.yml`: the `models: powerschool:` block with 16 hooks and the
  `sources: powerschool:` block, replayed from commit `409be13dc9`.
- `CLAUDE.md`: one sentence recording the second rebuild.

Dev builds go through `kippnewark` first (the consuming-district pattern in the
`dbt-local-dev` skill), then Camden and Paterson, then kippmiami for the archive
dry run. Dev tables land in `zz_cbini_<district>_powerschool`.

---

### Task 1: Pass identity and school columns through `base_powerschool__final_grades`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/base/base_powerschool__final_grades.sql`
- Modify:
  `src/dbt/powerschool/models/sis/base/properties/base_powerschool__final_grades.yml`

**Interfaces:**

- Consumes: `base_powerschool__course_enrollments` columns `students_dcid`,
  `students_student_number`, `school_abbreviation`, `school_level`, which it
  already carries (the `sec.*` star brings the school columns, and the students
  join brings the identity columns).
- Produces: `base_powerschool__final_grades` with 4 new columns:
  `students_dcid int64`, `students_student_number int64`,
  `school_abbreviation string`, `school_level string`. Task 2's
  `int_powerschool__gpa_term` reads `students_student_number` from here for its
  current-year branch.

- [ ] **Step 1: Add the 4 columns to the `enr_termbins` CTE**

In `base_powerschool__final_grades.sql`, the first CTE selects a column list
from `enr`. After the line `enr.school_name,` add:

```sql
            enr.students_dcid,
            enr.students_student_number,
            enr.school_abbreviation,
            enr.school_level,
```

Every later CTE uses `et.*` or `*`, so the columns flow to the `y1` CTE with no
further edit.

- [ ] **Step 2: Add the 4 columns to the final select**

In the final `select`, after the line `y1.school_name,` add:

```sql
    y1.students_dcid,
    y1.students_student_number,
    y1.school_abbreviation,
    y1.school_level,
```

- [ ] **Step 3: Add the columns to the properties file**

In `base_powerschool__final_grades.yml`, after the `- name: schoolid` block add:

```yaml
- name: students_dcid
  data_type: int64
- name: students_student_number
  data_type: int64
  config:
    meta:
      contains_pii: true
- name: school_name
  data_type: string
- name: school_abbreviation
  data_type: string
- name: school_level
  data_type: string
```

`school_name` was already an output column with no YAML entry; this adds it.

- [ ] **Step 4: Build in Newark dev and check parity**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippnewark
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod --select base_powerschool__final_grades
```

Expected: the model and its tests pass. Then via the BigQuery MCP:

```sql
select
    'dev' as side,
    count(*) as n,
    countif(students_student_number is null) as null_sn,
    countif(school_level is null) as null_level,
from `teamster-332318.zz_cbini_kippnewark_powerschool.base_powerschool__final_grades`
union all
select 'prod', count(*), null, null,
from `teamster-332318.kippnewark_powerschool.base_powerschool__final_grades`
```

Expected: the 2 counts are equal, and both null counts are 0. Course enrollments
inner-joins students and sections, so no row can lack either. A count difference
is live drift on a current-year table; re-run both sides within the same minute
before treating it as a bug.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/powerschool/models/sis/base/base_powerschool__final_grades.sql src/dbt/powerschool/models/sis/base/properties/base_powerschool__final_grades.yml </dev/null
```

Write `/workspaces/teamster/.claude/scratch/commit-msg.txt`:

```text
feat(powerschool): pass student identity and school columns through base_powerschool__final_grades

Refs #5228

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity add src/dbt/powerschool/models/sis/base/base_powerschool__final_grades.sql src/dbt/powerschool/models/sis/base/properties/base_powerschool__final_grades.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

---

### Task 2: Add identity and school columns to the 3 GPA intermediates

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_term.sql`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative_year.sql`
- Modify: the 3 matching files under
  `src/dbt/powerschool/models/sis/intermediate/properties/`

**Interfaces:**

- Consumes: `stg_powerschool__students` (`id`, `dcid`, `student_number`) and
  `stg_powerschool__schools` (`school_number`, `name`, `abbreviation`,
  `school_level`).
- Produces: each of the 3 models gains `students_dcid int64`,
  `students_student_number int64`, `school_name string`,
  `school_abbreviation string`, `school_level string`. Grain is unchanged:
  `(studentid, schoolid, yearid, term_name)`, `(studentid, schoolid)`, and
  `(studentid, schoolid, academic_year)`. PR B's kipptaf readers join on
  `students_student_number`.

`int_powerschool__gpa_term_current` and `int_powerschool__gpa_term_pivot` list
their columns explicitly and do not change. No kipptaf reader needs identity on
them.

- [ ] **Step 1: `int_powerschool__gpa_term`, join on the final select**

`stg_powerschool__students` also has `schoolid` and `yearid` columns, so every
unqualified column in the final select must take the `gc` alias or BigQuery
reports "Column name schoolid is ambiguous". Replace the final
`select ... from gpa_calcs` block (everything after the `gpa_calcs` CTE's
closing parenthesis) with:

```sql
select
    gc.studentid,
    gc.schoolid,
    gc.yearid,
    gc.storecode as term_name,
    gc.semester,
    gc.is_current,
    gc.gpa_points_total_term,
    gc.gpa_term,
    gc.gpa_points_total_y1,
    gc.gpa_y1,
    gc.gpa_y1_unweighted,
    gc.n_failing_y1,
    gc.total_credit_hours_term,
    gc.total_credit_hours_y1,

    s.dcid as students_dcid,
    s.student_number as students_student_number,

    sch.name as school_name,
    sch.abbreviation as school_abbreviation,
    sch.school_level,

    round(gc.grade_avg_term, 0) as grade_avg_term,
    round(gc.grade_avg_y1, 0) as grade_avg_y1,
    round(gc.weighted_gpa_points_term, 2) as weighted_gpa_points_term,
    round(gc.weighted_gpa_points_y1, 2) as weighted_gpa_points_y1,
    round(
        gc.weighted_gpa_points_y1_unweighted, 2
    ) as weighted_gpa_points_y1_unweighted,

    /* gpa semester */
    sum(gc.gpa_points_total_term) over (
        partition by gc.studentid, gc.yearid, gc.semester
    ) as gpa_points_total_semester,

    round(
        sum(gc.weighted_gpa_points_term) over (
            partition by gc.studentid, gc.yearid, gc.semester
        ),
        2
    ) as weighted_gpa_points_semester,

    round(
        sum(gc.total_credit_hours_y1) over (
            partition by gc.studentid, gc.yearid, gc.semester
        ),
        2
    ) as total_credit_hours_semester,

    round(
        avg(gc.grade_avg_term) over (
            partition by gc.studentid, gc.yearid, gc.semester
        ),
        0
    ) as grade_avg_semester,

    round(
        safe_divide(
            sum(gc.weighted_gpa_points_term) over (
                partition by gc.studentid, gc.yearid, gc.semester
            ),
            sum(gc.total_credit_hours_term) over (
                partition by gc.studentid, gc.yearid, gc.semester
            )
        ),
        2
    ) as gpa_semester,
from gpa_calcs as gc
left join {{ ref("stg_powerschool__students") }} as s on gc.studentid = s.id
left join
    {{ ref("stg_powerschool__schools") }} as sch on gc.schoolid = sch.school_number
```

The window expressions are unchanged except for the `gc.` prefix. `students.id`
is unique and `schools.school_number` is unique, so the joins add no rows.

- [ ] **Step 2: `int_powerschool__gpa_cumulative`, join on the final select**

Replace the final `select ... from needed_gpa` block with:

```sql
select
    ng.studentid,
    ng.schoolid,
    ng.earned_credits_cum,
    ng.potential_credits_cum,
    ng.earned_credits_cum_projected,
    ng.earned_credits_cum_projected_s1,
    ng.potentialcrhrs_projected as potential_gpa_credits_cum_projected,
    ng.potentialcrhrs_current as potential_gpa_credits_current_year,

    s.dcid as students_dcid,
    s.student_number as students_student_number,

    sch.name as school_name,
    sch.abbreviation as school_abbreviation,
    sch.school_level,

    round(safe_divide(ng.weighted_points, ng.potentialcrhrs), 2) as cumulative_y1_gpa,
    round(
        safe_divide(ng.unweighted_points, ng.potentialcrhrs), 2
    ) as cumulative_y1_gpa_unweighted,
    round(
        safe_divide(ng.weighted_points_projected, ng.potentialcrhrs_projected), 2
    ) as cumulative_y1_gpa_projected,
    round(
        safe_divide(
            ng.weighted_points_projected_s1, ng.potentialcrhrs_projected_s1
        ),
        2
    ) as cumulative_y1_gpa_projected_s1,
    round(
        safe_divide(
            ng.weighted_points_projected_s1_unweighted,
            ng.potentialcrhrs_projected_s1
        ),
        2
    ) as cumulative_y1_gpa_projected_s1_unweighted,
    round(
        safe_divide(
            ng.weighted_points_projected_unweighted, ng.potentialcrhrs_projected
        ),
        2
    ) as cumulative_y1_gpa_projected_unweighted,
    round(
        safe_divide(ng.weighted_points_core, ng.potentialcrhrs_core), 2
    ) as core_cumulative_y1_gpa,

    round(ng.gpa_needed_raw, 2) as gpa_needed_for_cumulative_3_0,

    round(ng.gpa_needed_raw, 2)
    <= round(ng.gpa_max_current_raw, 2) as is_cumulative_3_0_attainable,
from needed_gpa as ng
left join {{ ref("stg_powerschool__students") }} as s on ng.studentid = s.id
left join
    {{ ref("stg_powerschool__schools") }} as sch on ng.schoolid = sch.school_number
```

- [ ] **Step 3: `int_powerschool__gpa_cumulative_year`, wrap the union**

The model ends in a `union all` of 2 CTEs. Turn that union into a CTE and join
on a new final select. Replace everything from the first `select` after the
`projected_current_year` CTE's closing parenthesis to the end of the file with:

```sql
    unioned as (
        select
            studentid,
            schoolid,
            academic_year,
            grade_level,
            earned_credits_cum,
            potential_gpa_credits_cum,
            cumulative_y1_gpa,
            cumulative_y1_gpa_unweighted,
            is_projected,
        from completed_years

        union all

        select
            studentid,
            schoolid,
            academic_year,
            grade_level,
            earned_credits_cum,
            potential_gpa_credits_cum,
            cumulative_y1_gpa,
            cumulative_y1_gpa_unweighted,
            is_projected,
        from projected_current_year
    )

select
    u.studentid,
    u.schoolid,
    u.academic_year,
    u.grade_level,
    u.earned_credits_cum,
    u.potential_gpa_credits_cum,
    u.cumulative_y1_gpa,
    u.cumulative_y1_gpa_unweighted,
    u.is_projected,

    s.dcid as students_dcid,
    s.student_number as students_student_number,

    sch.name as school_name,
    sch.abbreviation as school_abbreviation,
    sch.school_level,
from unioned as u
left join {{ ref("stg_powerschool__students") }} as s on u.studentid = s.id
left join
    {{ ref("stg_powerschool__schools") }} as sch on u.schoolid = sch.school_number
```

The `projected_current_year` CTE's closing `)` must become `),` so `unioned`
chains onto the `with` list.

- [ ] **Step 4: Properties files, columns and PII**

In each of the 3 properties files, after the `- name: schoolid` block, add:

```yaml
- name: students_dcid
  data_type: int64
- name: students_student_number
  data_type: int64
  config:
    meta:
      contains_pii: true
- name: school_name
  data_type: string
- name: school_abbreviation
  data_type: string
- name: school_level
  data_type: string
```

- [ ] **Step 5: Unit test inputs**

`int_powerschool__gpa_cumulative.yml` has unit test
`unit_gpa_cumulative_needed_gpa` and `int_powerschool__gpa_cumulative_year.yml`
has `unit_gpa_cumulative_year_running_and_projected`. In each, under `given:`,
add 2 empty inputs after the existing ones:

```yaml
- input: ref('stg_powerschool__students')
  rows: []
- input: ref('stg_powerschool__schools')
  rows: []
```

The joins are left joins, so the empty inputs leave every expected row intact.
The `expect` rows do not list the new columns, and dbt compares only the columns
an expected row names, so no `expect` edit is needed.

- [ ] **Step 6: Build in Newark dev, run the unit tests, check parity**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod --select int_powerschool__gpa_term int_powerschool__gpa_cumulative int_powerschool__gpa_cumulative_year
```

Expected: 3 models, their data tests, and both unit tests pass. `dbt build` runs
unit tests before the model. A unit test failure that names
`stg_powerschool__students` or `stg_powerschool__schools` as "node not found"
means Step 5 missed a file.

Then, one query per model, via the BigQuery MCP:

```sql
select
    'dev' as side,
    count(*) as n,
    count(distinct format('%T|%T', studentid, schoolid)) as n_keys,
    countif(students_student_number is null) as null_sn,
    countif(school_name is null) as null_school,
from `teamster-332318.zz_cbini_kippnewark_powerschool.int_powerschool__gpa_cumulative`
union all
select
    'prod',
    count(*),
    count(distinct format('%T|%T', studentid, schoolid)),
    null,
    null,
from `teamster-332318.kippnewark_powerschool.int_powerschool__gpa_cumulative`
```

For `gpa_term` the key is
`format('%T|%T|%T|%T', studentid, schoolid, yearid, term_name)`; for
`gpa_cumulative_year` it is
`format('%T|%T|%T', studentid, schoolid, academic_year)`.

Expected: `n` and `n_keys` equal across sides for all 3 models. `null_sn` is 0.
`null_school` may be small but non-zero on `gpa_term` and `gpa_cumulative_year`:
a stored grade can carry a `schoolid` that is not in `schools` (transfer
credit). Record the count; a non-zero value is not a failure. If `null_sn` is
non-zero, a `studentid` on stored grades has no students row, which is a data
problem to report, not fix.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_term.sql src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative_year.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_term.yml src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative_year.yml </dev/null
```

Commit message:

```text
feat(powerschool): carry student identity and school columns on the GPA intermediates

Left joins to students and schools on gpa_term, gpa_cumulative, and
gpa_cumulative_year; grain unchanged. Unit tests gain empty inputs for the 2
new refs.

Refs #5228

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity add src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_term.sql src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative_year.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_term.yml src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative.yml src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_cumulative_year.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

---

### Task 3: New `int_powerschool__calendar_day`

**Files:**

- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__calendar_day.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__calendar_day.yml`
- Read only:
  `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__calendar_day.yml`
  for the staging column list and types.

**Interfaces:**

- Consumes: `stg_powerschool__calendar_day` (every column),
  `stg_powerschool__terms` (`schoolid`, `firstday`, `lastday`, `isyearrec`,
  `yearid`, `academic_year`), `stg_powerschool__schools` (`school_number`,
  `name`, `abbreviation`, `school_level`, `schoolcity`).
- Produces: one row per staging calendar day, same `id`, plus `yearid int64`,
  `academic_year int64`, `school_name string`, `school_abbreviation string`,
  `school_level string`, `schoolcity string`. PR B's
  `int_students__calendar_day` and `int_google_sheets__dibels_pm_expectations`
  read these.

- [ ] **Step 1: Write the model**

`int_powerschool__calendar_day.sql`:

```sql
select
    cd.*,

    t.yearid,
    t.academic_year,

    sch.name as school_name,
    sch.abbreviation as school_abbreviation,
    sch.school_level,
    sch.schoolcity,
from {{ ref("stg_powerschool__calendar_day") }} as cd
/* left join: a day with no covering year term keeps flowing with a null year,
   which is what kipptaf's int_students__calendar_day does today */
left join
    {{ ref("stg_powerschool__terms") }} as t
    on cd.schoolid = t.schoolid
    and cd.date_value between t.firstday and t.lastday
    and t.isyearrec = 1
left join {{ ref("stg_powerschool__schools") }} as sch on cd.schoolid = sch.school_number
```

- [ ] **Step 2: Write the properties file**

Copy the `columns:` list from `stg_powerschool__calendar_day.yml` (names and
`data_type` only; drop descriptions if any are long) and append the 6 new
columns. The file:

```yaml
models:
  - name: int_powerschool__calendar_day
    description: >-
      One row per PowerSchool calendar day with the covering year term and the
      school's name, abbreviation, level, and city attached, so consumers do not
      join terms or schools themselves. Left joins: a day outside every year
      term has a null yearid and academic_year.
    data_tests:
      - unique:
          column_name: id
          config:
            severity: error
    columns:
      # every column of stg_powerschool__calendar_day, copied from its
      # properties file, then:
      - name: yearid
        data_type: int64
      - name: academic_year
        data_type: int64
      - name: school_name
        data_type: string
      - name: school_abbreviation
        data_type: string
      - name: school_level
        data_type: string
      - name: schoolcity
        data_type: string
```

Replace the comment with the real copied list before committing. The `unique`
test on `id` is the grain guard: if 2 year terms ever overlap for one school and
date, the join fans out and the test errors.

- [ ] **Step 3: Build in Newark dev and check the count**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod --select int_powerschool__calendar_day
```

Expected: the model and the `unique` test pass. Then:

```sql
select
    'dev' as side,
    count(*) as n,
    countif(yearid is null) as null_year,
    countif(school_name is null) as null_school,
from `teamster-332318.zz_cbini_kippnewark_powerschool.int_powerschool__calendar_day`
union all
select 'prod_staging', count(*), null, null,
from `teamster-332318.kippnewark_powerschool.stg_powerschool__calendar_day`
```

Expected: equal `n`. `null_year` may be non-zero (days outside any year term);
record it. `null_school` should be 0.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/powerschool/models/sis/intermediate/int_powerschool__calendar_day.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__calendar_day.yml </dev/null
```

Commit message:

```text
feat(powerschool): add int_powerschool__calendar_day with year term and school columns

Refs #5228

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity add src/dbt/powerschool/models/sis/intermediate/int_powerschool__calendar_day.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__calendar_day.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

---

### Task 4: `entry_school_abbreviation` on `base_powerschool__student_enrollments`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/base/base_powerschool__student_enrollments.sql`
- Modify:
  `src/dbt/powerschool/models/sis/base/properties/base_powerschool__student_enrollments.yml`

**Interfaces:**

- Consumes: `entry_schoolid` from the `with_boy_status_window` CTE, and
  `stg_powerschool__schools.abbreviation`.
- Produces: `entry_school_abbreviation string`, null when `entry_schoolid` is
  null. PR B's `int_kippadb__roster` reads it in place of its own schools join.

- [ ] **Step 1: Add the column and the second schools join**

In the final select, after the line `sch.abbreviation as school_abbreviation,`
add:

```sql
    entry_sch.abbreviation as entry_school_abbreviation,
```

After the existing join

```sql
inner join
    {{ ref("stg_powerschool__schools") }} as sch on enr.schoolid = sch.school_number
```

add:

```sql
left join
    {{ ref("stg_powerschool__schools") }} as entry_sch
    on enr.entry_schoolid = entry_sch.school_number
```

`entry_schoolid` is a per-student max over the window CTE, one value per
student, so the join is 1:1 and adds no rows.

- [ ] **Step 2: Properties file**

After the `- name: school_abbreviation` block add:

```yaml
- name: entry_school_abbreviation
  data_type: string
  description: >-
    Abbreviation of the school the student first enrolled in within the network
    (entry_schoolid). Null when entry_schoolid is null.
```

- [ ] **Step 3: Build in Newark dev and check parity**

```bash
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod --select base_powerschool__student_enrollments
```

Expected: the model and its tests pass. Then:

```sql
select
    'dev' as side,
    count(*) as n,
    countif(entry_schoolid is not null and entry_school_abbreviation is null) as unmapped,
from `teamster-332318.zz_cbini_kippnewark_powerschool.base_powerschool__student_enrollments`
union all
select 'prod', count(*), null,
from `teamster-332318.kippnewark_powerschool.base_powerschool__student_enrollments`
```

Expected: equal `n`; `unmapped` is 0.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/powerschool/models/sis/base/base_powerschool__student_enrollments.sql src/dbt/powerschool/models/sis/base/properties/base_powerschool__student_enrollments.yml </dev/null
```

Commit message:

```text
feat(powerschool): add entry_school_abbreviation to base_powerschool__student_enrollments

Refs #5228

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity add src/dbt/powerschool/models/sis/base/base_powerschool__student_enrollments.sql src/dbt/powerschool/models/sis/base/properties/base_powerschool__student_enrollments.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

---

### Task 5: Build the 6 changed models in Camden and Paterson

**Files:** none modified. Verification only.

**Interfaces:**

- Consumes: the 6 models from Tasks 1 to 4.
- Produces: parity evidence for the PR body.

- [ ] **Step 1: Camden**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippcamden
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippcamden --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippcamden/target/prod --select base_powerschool__final_grades base_powerschool__student_enrollments int_powerschool__gpa_term int_powerschool__gpa_cumulative int_powerschool__gpa_cumulative_year int_powerschool__calendar_day
```

Expected: 6 models, tests, and 2 unit tests pass. Run the Task 1, 2, 3, and 4
parity queries with `kippcamden` in place of `kippnewark` in both dataset names.
Expected: same pattern of results.

- [ ] **Step 2: Paterson**

Same 2 commands with `kipppaterson`. Paterson disables
`int_powerschool__section_grade_config`; none of the 6 models read it. Expected:
same results.

- [ ] **Step 3: Record**

Write every count pair to `/workspaces/teamster/.claude/scratch/pr-a-parity.md`
(gitignored), one table per region. Counts only. Task 7 quotes them.

---

### Task 6: Re-include the package in kippmiami with the 16 archive hooks

**Files:**

- Modify: `src/dbt/kippmiami/packages.yml`
- Modify: `src/dbt/kippmiami/dbt_project.yml`
- Modify: `src/dbt/kippmiami/CLAUDE.md` (the PowerSchool paragraph)

**Interfaces:**

- Consumes: the `powerschool` package with the ODBC staging variant and the 58
  frozen externals at
  `gs://teamster-kippmiami/dagster/kippmiami/powerschool/<table>/*`.
- Produces: about 120 `kippmiami_powerschool.*` tables once the user
  materializes in prod, now including `int_powerschool__calendar_day` and the
  new columns on the other 5 models.

- [ ] **Step 1: Add the package**

In `src/dbt/kippmiami/packages.yml`, under `packages:`, after
`- local: ../focus` add:

```yaml
- local: ../powerschool
```

- [ ] **Step 2: Replay the `models:` and `sources:` blocks from commit
      `409be13dc9`**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity show 409be13dc9 -- src/dbt/kippmiami/dbt_project.yml > /workspaces/teamster/.claude/scratch/pr1-hooks.diff
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity apply /workspaces/teamster/.claude/scratch/pr1-hooks.diff
```

If `apply` fails because the surrounding lines moved, apply it by hand: the diff
adds a `powerschool:` block under `models:` (sibling of `focus:` and
`renlearn:`) and a top-level `sources:` block. Then add the 16th hook. In the
`odbc:` block, after the `stg_powerschool__terms:` hook, add:

```yaml
stg_powerschool__calendar_day:
  +post-hook: delete from {{ this }} where date_value >= '2026-07-01'
```

This is the hook `src/dbt/kippmiami/CLAUDE.md` records as missing from the first
rebuild (#5224 deleted those rows by hand).

- [ ] **Step 3: Install and parse**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippmiami
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippmiami --target dev
uv run dbt ls --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippmiami --target dev --resource-type model --output path | grep -c 'sis/staging/odbc/'
uv run dbt ls --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippmiami --target dev --resource-type model --output name | grep -c 'int_powerschool__calendar_day'
```

Expected: parse succeeds; the first count is the same as PR 1 reported (82 ODBC
staging models enabled minus the ones the replayed block disables); the second
count is 1.

- [ ] **Step 4: Stage the externals into your dev schema and build the package**

```bash
uv run dbt run-operation stage_external_sources --args "select: powerschool" --vars '{ext_full_refresh: true}' --target dev --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippmiami
uv run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity/src/dbt/kippmiami --target dev --select package:powerschool
```

This lands in `zz_cbini_kippmiami_powerschool`, so prod is untouched. Expected:
every model builds; `severity: warn` data tests may warn on frozen data, record
any warning for the PR body. Run in the foreground; it takes several minutes.

- [ ] **Step 5: Verify the new columns against the dev archive**

Identity check, expected `bare` 0 and `null_sn` 0 on all 3:

```sql
select 'gpa_term' as t, countif(students_student_number < 8400000000) as bare, countif(students_student_number is null) as null_sn, count(*) as n
from `teamster-332318.zz_cbini_kippmiami_powerschool.int_powerschool__gpa_term`
union all select 'gpa_cumulative', countif(students_student_number < 8400000000), countif(students_student_number is null), count(*)
from `teamster-332318.zz_cbini_kippmiami_powerschool.int_powerschool__gpa_cumulative`
union all select 'gpa_cumulative_year', countif(students_student_number < 8400000000), countif(students_student_number is null), count(*)
from `teamster-332318.zz_cbini_kippmiami_powerschool.int_powerschool__gpa_cumulative_year`
```

Row parity against prod for the 3 GPA tables plus `calendar_day`:

```sql
select 'dev' as side, count(*) as n
from `teamster-332318.zz_cbini_kippmiami_powerschool.int_powerschool__gpa_term`
union all
select 'prod', count(*)
from `teamster-332318.kippmiami_powerschool.int_powerschool__gpa_term`
```

Repeat for `int_powerschool__gpa_cumulative`,
`int_powerschool__gpa_cumulative_year`, and compare
`int_powerschool__calendar_day` (dev) to `stg_powerschool__calendar_day` (prod).
Expected: equal counts (prod values on 2026-09-09: 16,512 / 3,053 / 5,975).

Bound check on the 16th hook, expected 0:

```sql
select countif(date_value >= '2026-07-01') as over_bound, count(*) as n
from `teamster-332318.zz_cbini_kippmiami_powerschool.stg_powerschool__calendar_day`
```

Append every result to `/workspaces/teamster/.claude/scratch/pr-a-parity.md`.

- [ ] **Step 6: Confirm the Dagster code location loads**

Write `tests/dagster/test_zz_kippmiami_defs.py` in the worktree:

```python
import subprocess


def test_kippmiami_definitions_validate():
    subprocess.check_output(
        [
            "uv",
            "run",
            "dagster",
            "definitions",
            "validate",
            "-m",
            "teamster.code_locations.kippmiami.definitions",
        ],
        cwd="/workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity",
    )
```

Run from the worktree:

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity && uv run pytest tests/dagster/test_zz_kippmiami_defs.py -s
```

Expected: pass. Delete the test file after it passes. If validation fails on the
external asset keys, stop and report; do not add producer assets.

- [ ] **Step 7: Record the second rebuild in kippmiami CLAUDE.md**

In `src/dbt/kippmiami/CLAUDE.md`, in the PowerSchool paragraph, replace the
sentence beginning "The rebuild ran 2026-09-09 (#5012)" so the paragraph reads
that the archive was rebuilt on 2026-09-09 (#5012) and again after #5228 to add
identity and school columns to the GPA, final grades, calendar day, and student
enrollment models; the package is re-included for each rebuild and removed
after. Replace the trailing "A 16th hook belongs in that recipe" sentences with
one sentence saying the 16th hook (`stg_powerschool__calendar_day`, delete
`date_value >= '2026-07-01'`) is now in the recipe. Keep the rest of the
paragraph. In the "Source Packages" section, the sentence "Miami does not use
`edplan`, `overgrad`, `pearson`, `powerschool`, or `titan`" stays true after PR
B removes the package again, so leave it.

- [ ] **Step 8: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml src/dbt/kippmiami/CLAUDE.md </dev/null
```

Commit message:

```text
chore(kippmiami): re-include the powerschool package with the 16 archive hooks for the second rebuild

Refs #5228

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity add src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml src/dbt/kippmiami/CLAUDE.md src/dbt/kippmiami/package-lock.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

`package-lock.yml` changes when `dbt deps` adds the package; commit it, as PR 1
did.

---

### Task 7: Push and open the PR

**Files:**

- Create: `/workspaces/teamster/.claude/scratch/pr-a-body.md` (gitignored)

- [ ] **Step 1: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-powerschool-package-identity push
```

The branch tracks `origin` already.

- [ ] **Step 2: Write the PR body from the template**

Copy `.github/pull_request_template.md` to
`/workspaces/teamster/.claude/scratch/pr-a-body.md` and fill it in. Keep every
template line. One line per paragraph, no hard wraps. Summary:

> When merged, this pull request will give the shared `powerschool` package's
> GPA, final grades, calendar day, and student enrollment models the student
> identity and school columns that kipptaf joins for today
> (`students_student_number`, `school_name`, `school_abbreviation`,
> `school_level`, and `entry_school_abbreviation`), and re-include the package
> in `kippmiami` with the 16 archive hooks so one prod build lands those columns
> in the Miami archive. kipptaf is unchanged here; PR B (#5228) reads the new
> columns, drops Miami from `stg_powerschool__students` and 14 more unions, and
> removes the package from kippmiami again.

Reviewer Notes, one line each: every new join is a left join and every changed
model's row count equals prod in all 3 NJ regions;
`int_powerschool__calendar_day` is new and guarded by a `unique` test on `id`;
the 2 GPA unit tests gain empty inputs for the 2 new refs; the hooks are the
#5201 set plus the `calendar_day` bound #5224 recorded; dbt Cloud CI builds
kipptaf only and proves nothing here.

PII: `students_student_number` is tagged on 4 package models; state that.

"For Claude": paste the count tables from
`/workspaces/teamster/.claude/scratch/pr-a-parity.md`, any `severity: warn`
output from Task 6 Step 4, and the null-school and null-year counts from Tasks 2
and 3. Check the self-review boxes that apply. Leave
`stage_external_sources --target staging` unchecked and say why: the kippmiami
externals are prod-only and CI does not build kippmiami.

End the body with `Refs #5228` and `Refs #5012`, then the line
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

- [ ] **Step 3: Open the PR**

Use `mcp__github__create_pull_request` with `owner: TEAMSchools`,
`repo: teamster`, `head: cbini/refactor/claude-powerschool-package-identity`,
`base: main`, title
`feat(powerschool): carry student identity and school columns on the package facts and rebuild the Miami archive (PR A)`,
and the body from Step 2. Confirm the returned title and body match.

- [ ] **Step 4: Watch CI and review**

Invoke `pr-ci-review`. Expected: Trunk passes; dbt Cloud CI passes with no
kipptaf models selected; the Dagster Cloud branch deployments for the 4
districts build. When `claude-review` posts, invoke
`superpowers:receiving-code-review` before acting on it.

---

## After merge (user-run, not part of this plan's commits)

1. NJ regions: the 6 changed models materialize on each region's next upstream
   update. Confirm in Dagster that
   `kippnewark/powerschool/int_powerschool__calendar_day` and the 5 others have
   a materialization in each region.
1. Miami: Dagster UI, code location `kippmiami`, asset group `powerschool`,
   materialize all. Branch deployments read `gs://teamster-test`, so this runs
   on prod.
1. Claude re-runs the Task 6 Step 5 queries against `kippmiami_powerschool`.
   Expected: identical to dev. Then PR B, with its own plan.

## Self-review notes

- Spec coverage: "Package changes (PR A)" table rows map to Tasks 1 to 4; the
  PII line is in Tasks 1 and 2; the kippmiami include is Task 6; "Delivery" step
  1 is Task 7 and step 2 is "After merge". The spec's kipptaf sections are PR B.
- Spec correction folded in here: the spec says `gpa_term_pivot` and
  `gpa_term_current` "inherit" the new columns. Both list columns explicitly and
  do not. No kipptaf reader needs identity on them, so they are unchanged.
- Type consistency: the 5 new column names are identical in every task and in
  the spec. `entry_school_abbreviation` appears only in Task 4 and the spec.
- The Miami archive dry run in Task 6 covers the spec's "Miami archive" checks
  in dev; the same queries run in prod after merge.
