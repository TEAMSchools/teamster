# Enrollment week exit-date boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the weekly enrollment spines count a stint's enrolled days
correctly per SIS, give `_subjects_weeks` one row per student-week-discipline,
and simplify the six consumers that worked around the old behavior.

**Architecture:** One new column, `last_enrolled_date`, is defined at the
PowerSchool/Focus union in `int_students__student_enrollments` and flows down
the existing `select *` chain. Both spines compute their flags from it;
`_subjects_weeks` also joins on it and dedups with the pick the topline models
already use. Consumers drop their own dedup or filter.

**Tech Stack:** dbt (BigQuery), `dbt_utils.deduplicate`,
`dbt_utils.unique_combination_of_columns`, `dbt_utils.expression_is_true`.

**Spec:**
`docs/superpowers/specs/2026-09-23-enrollment-week-exit-boundary-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/fix/claude-enrollment-week-exit-boundary`
  (below, `$wt`). Every git call is `git -C $wt`; every file path is under
  `$wt`.
- Every dbt call is `uv run dbt ... --project-dir $wt/src/dbt/kipptaf`. Run
  `uv run dbt deps --project-dir $wt/src/dbt/kipptaf` once, in its own Bash
  call, before the first build.
- Local builds go to `--target dev` only, with
  `--defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
  Every changed model must be inside `--select`: `--favor-state` resolves any
  unselected upstream to prod, which would hide the change.
- No warehouse DDL or DML. The BigQuery MCP is SELECT-only.
- PowerSchool rule: `last_enrolled_date = date_sub(exitdate, interval 1 day)`.
  Focus rule: `last_enrolled_date = exitdate`. No region `if` anywhere.
- `_subjects_weeks` dedup:
  `partition_by="student_number, academic_year, week_start_monday, discipline"`,
  `order_by="is_enrolled_week desc, entrydate desc"`. No `_dbt_source_project`
  in the partition.
- `exitdate` keeps its meaning everywhere. Do not touch `days_enrolled` or any
  other `exitdate` use outside the files listed here.
- No student numbers, names or other row values in commits, the PR body or PR
  comments. Counts only.
- Before pushing SQL, YAML or markdown:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd `$wt`.

## Deviation from the spec

The spec's Testing section asks for a dbt unit test on
`int_extracts__student_enrollments_subjects_weeks`. This plan replaces it with
two model-level `dbt_utils.expression_is_true` tests plus the grain test, for
this reason: the model's upstream gains `last_enrolled_date` in this same PR,
and the repo's unit-test rule (`.claude/rules/dbt-yaml.md`, _dbt unit-test
fixtures_) says a same-PR column add fails dict fixtures in CI. The
`format: sql` fallback would have to spell out all ~300 columns of
`int_extracts__student_enrollments_subjects`. The data tests assert the same
three behaviors on real rows at every build.

## Review Focus

1. Miami one-day stints (`entrydate = exitdate`) must still produce their week
   row, flagged when the day is a Monday. Checked in Task 2 Step 6, query D.
2. Miami stints trimmed to nothing (`exitdate < entrydate`) must produce no week
   rows, as today. Checked in Task 2 Step 6, query D.
3. Graduate placeholders (null `exitdate`, grade 99) must produce no week rows,
   as today. Checked in Task 1 Step 5 and Task 2 Step 6, query D.
4. A week whose Monday is a holiday: an NJ stint exiting on the Tuesday (the
   week's first school day) gets no row, and a stint entering that Tuesday gets
   exactly one row with `is_enrolled_week` false. Checked in Task 2 Step 6,
   query B, and Task 3 Step 6.
5. A student who moves between two regions mid-week gets one row that week, not
   one per region. Covered by the grain test in Task 2 (it omits
   `_dbt_source_project`).

---

### Task 1: `last_enrolled_date` at the SIS union

**Files:**

- Modify:
  `$wt/src/dbt/kipptaf/models/students/intermediate/int_students__student_enrollments.sql`
  (`focus_conformed` CTE near line 107, `powerschool_conformed` CTE near line
  287, both branches of `with_region` near lines 306 and 397)
- Modify:
  `$wt/src/dbt/kipptaf/models/students/intermediate/properties/int_students__student_enrollments.yml`
- Modify:
  `$wt/src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments.yml`
- Modify:
  `$wt/src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_subjects.yml`

**Interfaces:**

- Produces: column `last_enrolled_date` (DATE) on
  `int_students__student_enrollments`, reaching
  `base_powerschool__student_enrollments`, `int_extracts__student_enrollments`,
  `int_extracts__student_enrollments_subjects` and
  `int_extracts__student_enrollments_weeks` through their existing `select *` /
  `co.*`. Null exactly where `exitdate` is null.

- [ ] **Step 1: Write the failing check**

Save this query as `<scratchpad>/t1_check.sql`. The `<scratchpad>` is the
session scratchpad path from the system prompt. The dev dataset is
`zz_cbini_extracts`; confirm with
`select schema_name from teamster-332318.region-us.INFORMATION_SCHEMA.SCHEMATA where schema_name like 'zz_cbini%'`.

```sql
select
    _dbt_source_project,
    countif(last_enrolled_date = date_sub(exitdate, interval 1 day)) as ps_rule,
    countif(last_enrolled_date = exitdate) as focus_rule,
    countif(last_enrolled_date is null and exitdate is null) as both_null,
    countif(
        (last_enrolled_date is null) != (exitdate is null)
    ) as null_mismatch,
    count(*) as n,
from `teamster-332318.zz_cbini_extracts.int_extracts__student_enrollments`
group by _dbt_source_project
```

Run it with the BigQuery MCP `execute_sql`. Expected now: FAIL with
`Unrecognized name: last_enrolled_date`, or `Not found` if the dev table does
not exist yet.

- [ ] **Step 2: Add the column in the Focus branch**

In `focus_conformed`, directly after `enr.exitdate,` (line 107), add:

```sql
            enr.exitdate as last_enrolled_date,
```

It stays in the `enr` plain-column group, so ST06 ordering is unchanged. The
roster trims each stint to the day before the next one starts, so `exitdate` is
already the inclusive last day.

- [ ] **Step 3: Add the column in the PowerSchool branch**

In `powerschool_conformed`, between the `_dbt_source_project` line and the
`initcap(...)` line, add the simple function (it must come before the nested
`initcap(regexp_extract(...))` for ST06):

```sql
    powerschool_conformed as (
        select
            *,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

            date_sub(exitdate, interval 1 day) as last_enrolled_date,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
        from union_relations
    ),
```

- [ ] **Step 4: List the column in both `with_region` branches**

`with_region` is a `union all corresponding`, which matches by name and errors
if the lists differ. In BOTH branches, directly after `exitdate,` (lines 306 and
397), add:

```sql
            last_enrolled_date,
```

- [ ] **Step 5: Document the column in three properties files**

In each of `int_students__student_enrollments.yml`,
`int_extracts__student_enrollments.yml` and
`int_extracts__student_enrollments_subjects.yml`, insert this entry directly
before the `- name:` entry that follows `- name: exitdate`. Match the file's
existing indentation (6 spaces before `- name`):

```yaml
- name: last_enrolled_date
  data_type: date
  description:
    Inclusive last day the student was enrolled in this stint. PowerSchool
    records exitdate as the first day the student is no longer enrolled, so
    PowerSchool stints use the day before exitdate; Focus trims each stint to
    the day before the next one starts, so Focus stints use exitdate unchanged.
    Null for graduate placeholder rows, which carry no exit date. Use this
    column, not exitdate, for any "enrolled on date X" test.
```

- [ ] **Step 6: Build the chain into dev**

Run (its own Bash call):

```bash
uv run dbt deps --project-dir $wt/src/dbt/kipptaf
```

Then:

```bash
uv run dbt build \
  --select int_students__student_enrollments base_powerschool__student_enrollments int_extracts__student_enrollments int_extracts__student_enrollments_subjects \
  --project-dir $wt/src/dbt/kipptaf --target dev \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  2>&1 | tail -n 30
```

Expected: `ERROR=0`. Warnings that also fire on main are acceptable; note them.

- [ ] **Step 7: Run the check and confirm it passes**

Run `<scratchpad>/t1_check.sql` again. Expected:

- kippnewark, kippcamden, kipppaterson: `ps_rule + both_null = n`,
  `null_mismatch = 0`.
- kippmiami: `focus_rule = n`, `both_null = 0`, `null_mismatch = 0`.

- [ ] **Step 8: Lint and commit**

```bash
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/students/intermediate/int_students__student_enrollments.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__student_enrollments.yml \
  src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments.yml \
  src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_subjects.yml \
  </dev/null 2>&1 | tail -n 20
git -C $wt add -u
git -C $wt commit -m "fix(dbt): add last_enrolled_date at the SIS union

PowerSchool exitdate is the first day not enrolled; Focus exitdate is
the last enrolled day. Each branch now states its own convention.

Refs #5504

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The two spines

**Files:**

- Modify:
  `$wt/src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_subjects_weeks.sql`
  (whole file; select list is lines 1-317, join lines 318-324)
- Modify:
  `$wt/src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_weeks.sql`
  (lines 17-23 and 35)
- Modify:
  `$wt/src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_subjects_weeks.yml`
- Modify:
  `$wt/src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_weeks.yml`

**Interfaces:**

- Consumes: `last_enrolled_date` from Task 1 on
  `int_extracts__student_enrollments_subjects` and
  `int_extracts__student_enrollments`.
- Produces: `int_extracts__student_enrollments_subjects_weeks` at one row per
  (`student_number`, `academic_year`, `week_start_monday`, `discipline`), with a
  new `last_enrolled_date` column. `is_enrolled_week` and `is_enrolled_week_end`
  on both spines are computed from `last_enrolled_date`.

- [ ] **Step 1: Add the tests to `_subjects_weeks` (they fail on the current
      SQL)**

In `int_extracts__student_enrollments_subjects_weeks.yml`, replace the model
`description:` block (lines 3-10) and add a `data_tests:` block between
`config:` and `columns:`:

```yaml
- name: int_extracts__student_enrollments_subjects_weeks
  description:
    One row per student, academic year, school week and discipline, built by
    expanding int_extracts__student_enrollments_subjects across the in-session
    weeks each stint covers. A stint covers a week when it starts on or before
    the week's last school day and its last_enrolled_date falls on or after the
    week's first school day. When two stints cover the same week (a mid-week
    transfer or re-entry), the row kept is the stint enrolled on the Monday, and
    otherwise the later stint.
  config:
    schema: extracts
  data_tests:
    - dbt_utils.unique_combination_of_columns:
        arguments:
          combination_of_columns:
            - student_number
            - academic_year
            - week_start_monday
            - discipline
        config:
          severity: error
    - dbt_utils.expression_is_true:
        arguments:
          expression:
            "not (_dbt_source_project != 'kippmiami' and is_enrolled_week and
            exitdate = week_start_monday)"
        config:
          severity: error
    - dbt_utils.expression_is_true:
        arguments:
          expression:
            "not (_dbt_source_project != 'kippmiami' and exitdate =
            school_week_start_date)"
        config:
          severity: error
  columns:
```

Replace the `is_enrolled_week` column entry (lines 440-445) with:

```yaml
- name: is_enrolled_week
  data_type: boolean
  description:
    True when the student was enrolled in this stint on the week's Monday,
    meaning week_start_monday falls between entrydate and last_enrolled_date.
- name: is_enrolled_week_end
  data_type: boolean
  description:
    True when the student was enrolled in this stint on the week's Sunday,
    meaning week_end_sunday falls between entrydate and last_enrolled_date.
```

Directly before the `- name: region` entry that follows `- name: exitdate`,
insert the `last_enrolled_date` entry, same text as Task 1 Step 5.

- [ ] **Step 2: Run the tests against prod and confirm they fail**

```bash
uv run dbt test --select int_extracts__student_enrollments_subjects_weeks \
  --project-dir $wt/src/dbt/kipptaf --target dev \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  2>&1 | tail -n 30
```

Expected: 3 FAIL, against the deferred prod view. The grain test fails on the
duplicate keys (74 measured on 2026-09-22 for AY2025+, more across all years).
The first expression test fails on the NJ Monday rows (206 measured for
AY2025+). The second fails on the exit-day rows (296 measured for AY2025+).
Record each count for the PR body.

- [ ] **Step 3: Rewrite `_subjects_weeks`**

Wrap the existing select in a CTE named `student_weeks` and dedup it, following
the pattern already used in `int_extracts__student_enrollments_weeks.sql`. The
full file becomes:

```sql
with
    student_weeks as (
        select
            co._dbt_source_relation,
            -- ...every existing co.* column line, unchanged, in the same order,
            -- with ONE addition directly after `co.exitdate,`:
            co.last_enrolled_date,
            -- ...
            co._dbt_source_project,

            cw.week_start_monday,
            cw.week_end_sunday,
            cw.quarter,
            cw.semester,
            cw.school_week_start_date,
            cw.school_week_end_date,
            cw.week_number_academic_year,
            cw.week_number_quarter,
            cw.is_current_week_mon_sun,
            cw.date_count,

            if(
                cw.week_start_monday between co.entrydate and co.last_enrolled_date,
                true,
                false
            ) as is_enrolled_week,

            if(
                cw.week_end_sunday between co.entrydate and co.last_enrolled_date,
                true,
                false
            ) as is_enrolled_week_end,
        from {{ ref("int_extracts__student_enrollments_subjects") }} as co
        inner join
            {{ ref("int_students__calendar_week") }} as cw
            on co.academic_year = cw.academic_year
            and co.schoolid = cw.schoolid
            and co._dbt_source_project = cw._dbt_source_project
            and co.entrydate <= cw.school_week_end_date
            and co.last_enrolled_date >= cw.school_week_start_date
    )

    {{
        dbt_utils.deduplicate(
            relation="student_weeks",
            partition_by="student_number, academic_year, week_start_monday, discipline",
            order_by="is_enrolled_week desc, entrydate desc",
        )
    }}
```

The `-- ...` lines above stand for the ~290 existing `co.<column>,` lines, lines
2-297 of the current file. Move them into the CTE unchanged; the only edits
inside the list are the one added line and re-indenting by 8 spaces. Do not keep
those `-- ...` comments in the file. Do not otherwise reorder or drop columns.
If sqlfluff flags ST03 on `student_weeks`, add
`# trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below`
above the CTE, as the rule file describes; `_weeks` currently passes without it,
so it is probably not needed.

- [ ] **Step 4: Fix the flags and the tie-break in `_weeks`**

In `int_extracts__student_enrollments_weeks.sql`, change both flags (lines
17-23) to:

```sql
            if(
                cw.week_start_monday between co.entrydate and co.last_enrolled_date,
                true,
                false
            ) as is_enrolled_week,

            if(
                cw.week_end_sunday between co.entrydate and co.last_enrolled_date,
                true,
                false
            ) as is_enrolled_week_end,
```

and the dedup `order_by` (line 35) to:

```sql
            order_by="is_enrolled_week desc, entrydate desc",
```

The join (academic_year + schoolid, no date bound) stays as it is: attrition and
the enrollment denominator need rows for the weeks after a student exits.

In `int_extracts__student_enrollments_weeks.yml`, insert the
`last_enrolled_date` entry (same text as Task 1 Step 5) directly before the
`- name: exitcode` entry.

- [ ] **Step 5: Build both spines into dev and run the tests**

```bash
uv run dbt build \
  --select int_students__student_enrollments base_powerschool__student_enrollments int_extracts__student_enrollments int_extracts__student_enrollments_subjects int_extracts__student_enrollments_subjects_weeks int_extracts__student_enrollments_weeks \
  --project-dir $wt/src/dbt/kipptaf --target dev \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  2>&1 | tail -n 30
```

Expected: `ERROR=0`. All three `_subjects_weeks` tests PASS, and the `_weeks`
grain test PASSES.

- [ ] **Step 6: Check the edge cases against the dev views**

Run each query with the BigQuery MCP. `dev` =
`teamster-332318.zz_cbini_extracts`, `prod` =
`teamster-332318.kipptaf_extracts`.

A. The issue's "fixed means", AY2025+, on dev:

```sql
select
    countif(
        _dbt_source_project != 'kippmiami'
        and exitdate = week_start_monday
        and is_enrolled_week
    ) as nj_exit_monday_flagged,
    countif(
        _dbt_source_project != 'kippmiami' and exitdate = school_week_start_date
    ) as ps_exit_on_first_school_day,
from `teamster-332318.zz_cbini_extracts.int_extracts__student_enrollments_subjects_weeks`
where academic_year >= 2025
```

Expected: both 0.

B. Holiday-Monday weeks (Review Focus 4). Stints entering on a week's first
school day when that day is not the Monday:

```sql
select countif(is_enrolled_week) as flagged, count(*) as n,
from `teamster-332318.zz_cbini_extracts.int_extracts__student_enrollments_subjects_weeks`
where
    academic_year >= 2025
    and entrydate = school_week_start_date
    and school_week_start_date > week_start_monday
```

Expected: `n > 0` and `flagged = 0`.

C. Miami is unchanged. Row count and flag count per academic year, dev against
prod, Miami only:

```sql
select 'dev' as side, academic_year, count(*) as n, countif(is_enrolled_week) as f,
from `teamster-332318.zz_cbini_extracts.int_extracts__student_enrollments_subjects_weeks`
where _dbt_source_project = 'kippmiami' and academic_year >= 2025
group by academic_year
union all
select 'prod', academic_year, count(*), countif(is_enrolled_week),
from `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments_subjects_weeks`
where _dbt_source_project = 'kippmiami' and academic_year >= 2025
group by academic_year
```

Expected: dev `n` is at most prod `n`. The only drop is Miami's own two-stint
keys (a Miami transfer week keeps one row now). Dev `f` equals prod `f` minus at
most that drop. Any other difference is a bug.

D. Edge stints produce the right number of rows (Review Focus 1-3):

```sql
with
    stints as (
        select student_number, entrydate, exitdate, grade_level, _dbt_source_project,
        from `teamster-332318.zz_cbini_extracts.int_extracts__student_enrollments`
        where academic_year >= 2025
    ),

    week_rows as (
        select student_number, entrydate, count(*) as n_weeks,
        from `teamster-332318.zz_cbini_extracts.int_extracts__student_enrollments_subjects_weeks`
        where academic_year >= 2025
        group by student_number, entrydate
    )

select
    countif(
        s._dbt_source_project = 'kippmiami' and s.entrydate = s.exitdate and w.n_weeks is null
    ) as miami_one_day_missing,
    countif(
        s._dbt_source_project = 'kippmiami' and s.exitdate < s.entrydate and w.n_weeks is not null
    ) as miami_trimmed_present,
    countif(s.exitdate is null and w.n_weeks is not null) as placeholder_present,
from stints as s
left join
    week_rows as w
    on s.student_number = w.student_number
    and s.entrydate = w.entrydate
```

Expected: `miami_trimmed_present = 0` and `placeholder_present = 0`.
`miami_one_day_missing` counts one-day stints on a non-school day or lost to a
same-week pick. Compare it with the same query against prod. The two numbers
must match, since Miami logic did not change.

- [ ] **Step 7: Lint and commit**

```bash
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_subjects_weeks.sql \
  src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_weeks.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_subjects_weeks.yml \
  src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_weeks.yml \
  </dev/null 2>&1 | tail -n 20
git -C $wt add -u
git -C $wt commit -m "fix(dbt): count enrolled weeks from last_enrolled_date

Both spines flag a week from last_enrolled_date, and the subjects spine
joins on it and keeps one row per student-week-discipline. The weeks
spine dedup gets an entrydate tie-break.

Refs #5504

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Consumers

**Files:**

- Modify:
  `$wt/src/dbt/kipptaf/models/topline/intermediate/int_topline__iready_diagnostic_weekly.sql`
  (lines 39-47 CTE, line 70 `from`)
- Modify:
  `$wt/src/dbt/kipptaf/models/topline/intermediate/int_topline__iready_lessons_weekly.sql`
  (lines 16-24 CTE, line 35 `from`)
- Modify:
  `$wt/src/dbt/kipptaf/models/topline/intermediate/int_topline__state_assessments_weekly.sql`
  (lines 20-28 CTE, lines 41 and 69 `from`)
- Modify:
  `$wt/src/dbt/kipptaf/models/topline/intermediate/int_topline__star_assessment_weekly.sql`
  (lines 18-26 CTE, line 61 `from`)
- Modify:
  `$wt/src/dbt/kipptaf/models/topline/intermediate/int_topline__formative_assessment_weekly.sql`
  (lines 46-48 `where`)
- Modify:
  `$wt/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_attrition_over_time.sql`
  (line 38)

**Interfaces:**

- Consumes: `_subjects_weeks` at one row per student-week-discipline (Task 2);
  `_weeks.is_enrolled_week` computed from `last_enrolled_date` (Task 2).
- Produces: no new columns. Each model's output columns and grain test are
  unchanged.

- [ ] **Step 1: Record the baseline for the check**

Before editing, run against prod and save the counts in the scratchpad:

```sql
select 'formative' as m, count(*) as n,
from `teamster-332318.kipptaf_topline.int_topline__formative_assessment_weekly`
union all
select 'iready_diagnostic', count(*),
from `teamster-332318.kipptaf_topline.int_topline__iready_diagnostic_weekly`
union all
select 'iready_lessons', count(*),
from `teamster-332318.kipptaf_topline.int_topline__iready_lessons_weekly`
union all
select 'state_assessments', count(*),
from `teamster-332318.kipptaf_topline.int_topline__state_assessments_weekly`
union all
select 'star', count(*),
from `teamster-332318.kipptaf_topline.int_topline__star_assessment_weekly`
```

- [ ] **Step 2: Drop the dedup CTE from the four topline models**

In each of the four files, delete the whole `subject_weeks_deduplicate as (...)`
CTE together with the comma that ends the `subject_weeks` CTE before it. Then
change every `from subject_weeks_deduplicate as <alias>` to
`from subject_weeks as <alias>`, keeping the alias. After the edit, in
`int_topline__iready_lessons_weekly.sql` the top of the file reads:

```sql
with
    subject_weeks as (
        select
            student_number,
            academic_year,
            week_start_monday,
            week_end_sunday,
            discipline,
            iready_subject,
            entrydate,
            is_enrolled_week,
        from {{ ref("int_extracts__student_enrollments_subjects_weeks") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
    )
```

and its main query reads `from subject_weeks as co`. In
`int_topline__iready_diagnostic_weekly.sql`,
`int_topline__state_assessments_weekly.sql` and
`int_topline__star_assessment_weekly.sql`, `subject_weeks` is followed by other
CTEs, so its closing `),` keeps its comma there. Remove only the deleted CTE's
text.

`entrydate` and `is_enrolled_week` stay in each `subject_weeks` select list only
if something else in the file reads them. Check with
`grep -n 'entrydate\|is_enrolled_week' <file>`. If the dedup was their only
reader, remove them from the list.

- [ ] **Step 3: Drop the flag filter from formative**

In `int_topline__formative_assessment_weekly.sql`, replace:

```sql
        where
            sw.is_enrolled_week
            and sw.academic_year >= {{ var("current_academic_year") - 1 }}
```

with:

```sql
        where sw.academic_year >= {{ var("current_academic_year") - 1 }}
```

- [ ] **Step 4: Reuse the flag in the attrition model**

In `rpt_tableau__student_attrition_over_time.sql`, replace line 38:

```sql
    if(co.week_start_monday between co.entrydate and co.exitdate, 0, 1) as is_attrition,
```

with:

```sql
    if(co.is_enrolled_week, 0, 1) as is_attrition,
```

- [ ] **Step 5: Build the consumers into dev**

Include every changed upstream so `--favor-state` does not read prod for them:

```bash
uv run dbt build \
  --select int_students__student_enrollments base_powerschool__student_enrollments int_extracts__student_enrollments int_extracts__student_enrollments_subjects int_extracts__student_enrollments_subjects_weeks int_extracts__student_enrollments_weeks int_topline__iready_diagnostic_weekly int_topline__iready_lessons_weekly int_topline__state_assessments_weekly int_topline__star_assessment_weekly int_topline__formative_assessment_weekly rpt_tableau__student_attrition_over_time rpt_tableau__iready_apm \
  --project-dir $wt/src/dbt/kipptaf --target dev \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  2>&1 | tail -n 30
```

Expected: `ERROR=0`, and every grain test on these models passes.

- [ ] **Step 6: Check formative against prod**

`zz_cbini_topline` is the dev dataset for topline models; confirm it with the
SCHEMATA query from Task 1 Step 1.

```sql
with
    dev as (
        select *,
        from `teamster-332318.zz_cbini_topline.int_topline__formative_assessment_weekly`
    ),

    prod as (
        select *,
        from `teamster-332318.kipptaf_topline.int_topline__formative_assessment_weekly`
    )

select
    countif(dev.student_number is null) as prod_keys_lost,
    countif(prod.student_number is null) as new_keys,
    countif(
        dev.student_number is not null
        and prod.student_number is not null
        and dev.is_mastery_running_int is distinct from prod.is_mastery_running_int
    ) as value_changes,
from dev
full join
    prod
    using (student_number, academic_year, week_start_monday, discipline, formative_strategy)
```

With `using`, the `student_number` null checks need the side-qualified columns.
If BigQuery rejects `dev.student_number` under `using`, switch to an explicit
`on` over the five columns.

Expected: `new_keys` is several thousand (about 7,000, Miami the largest share).
`prod_keys_lost` is 0 or limited to the NJ boundary weeks the fix removes.
`value_changes` is 0 or explained by prod table age. Rebuild times differ, so
spot-check any nonzero count against `administered_at`. Then confirm the new
keys are mid-week entries:

```sql
select countif(sw.is_enrolled_week) as new_keys_flagged, count(*) as new_keys,
from `teamster-332318.zz_cbini_topline.int_topline__formative_assessment_weekly` as d
left join
    `teamster-332318.kipptaf_topline.int_topline__formative_assessment_weekly` as p
    using (student_number, academic_year, week_start_monday, discipline, formative_strategy)
inner join
    `teamster-332318.zz_cbini_extracts.int_extracts__student_enrollments_subjects_weeks`
    as sw
    on d.student_number = sw.student_number
    and d.academic_year = sw.academic_year
    and d.week_start_monday = sw.week_start_monday
    and d.discipline = sw.discipline
where p.is_mastery_running_int is null and p.week_end_sunday is null
```

Expected: `new_keys_flagged = 0`. Every new key is a week the student was not
enrolled on the Monday.

- [ ] **Step 7: Row diff for the other four toplines**

Run Step 1's query against `zz_cbini_topline` and compare with the baseline.
Expected: each changes by a small amount, about the NJ boundary rows. Record the
four deltas for the PR body.

- [ ] **Step 8: Lint and commit**

```bash
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/topline/intermediate/int_topline__iready_diagnostic_weekly.sql \
  src/dbt/kipptaf/models/topline/intermediate/int_topline__iready_lessons_weekly.sql \
  src/dbt/kipptaf/models/topline/intermediate/int_topline__state_assessments_weekly.sql \
  src/dbt/kipptaf/models/topline/intermediate/int_topline__star_assessment_weekly.sql \
  src/dbt/kipptaf/models/topline/intermediate/int_topline__formative_assessment_weekly.sql \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_attrition_over_time.sql \
  </dev/null 2>&1 | tail -n 20
git -C $wt add -u
git -C $wt commit -m "fix(dbt): read the deduped subjects spine in topline models

Four topline models drop their own stint pick, formative stops dropping
mid-week-entry weeks, and attrition reuses the corrected flag.

Refs #5504

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Whole-consumer build, impact numbers, PR

**Files:** none changed. Produces the PR.

- [ ] **Step 1: Build every remaining consumer**

The models the spec lists under "No code change, values shift for NJ":

```bash
uv run dbt build \
  --select int_students__student_enrollments base_powerschool__student_enrollments int_extracts__student_enrollments int_extracts__student_enrollments_subjects int_extracts__student_enrollments_subjects_weeks int_extracts__student_enrollments_weeks rpt_gsheets__school_metrics_extract rpt_tableau__ddi_dashboard rpt_tableau__okrts_behavior int_topline__attendance_contacts int_topline__attendance_contacts_weekly int_topline__attendance_interventions_weekly int_topline__college_entrance_exams_weekly int_topline__college_matriculation_weekly int_topline__deanslist_incentives_weekly int_topline__gpa_cumulative_weekly int_topline__gpa_term_weekly int_topline__student_metrics \
  --project-dir $wt/src/dbt/kipptaf --target dev \
  --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  2>&1 | tail -n 30
```

Expected: `ERROR=0`. For any warning, check whether it fires against prod too
(`dbt test --select <model> --target dev --defer --state ...`) before treating
it as caused by this change.

- [ ] **Step 2: Measure Total Enrollment and attrition impact**

Find the Total Enrollment rows in `int_topline__student_metrics`. Read the model
near lines 277 and 295 for its indicator column and value, then compare
`sum(metric_value)` per region for the current academic year, dev against prod.
For attrition, compare `sum(is_attrition)` per region and academic year in
`rpt_tableau__student_attrition_over_time`, dev against prod. Record both tables
for the PR body, as aggregates per region with no student rows.

- [ ] **Step 3: Push and open the PR**

Invoke `pr-ci-review` first. Write the body to `<scratchpad>/pr-body.md` from
`.github/pull_request_template.md`, one line per paragraph with no hard wraps.
It must include:

- `Closes #5504`.
- The before/after counts from Task 2 Step 2 and Step 6.
- The formative, topline, Total Enrollment and attrition numbers.
- The membership evidence summary, with a link to the spec.
- A note that the change reverses #5386's per-stint grain on purpose, and why.
- The test deviation from the spec.

```bash
git -C $wt push
```

Then create the PR with `mcp__github__create_pull_request` (base `main`, head
`cbini/fix/claude-enrollment-week-exit-boundary`), and read back the title and
body to confirm they match.
