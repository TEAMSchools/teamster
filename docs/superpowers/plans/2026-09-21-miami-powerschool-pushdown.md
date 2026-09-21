# Miami PowerSchool Pushdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move every derivation `kipptaf` computes over frozen Miami PowerSchool
rows into the `powerschool` package, so the archive bakes the values once
instead of recomputing them on every read.

**Architecture:** 4 changes to the `powerschool` package (1 new intermediate, 3
column adds), one Miami archive re-bake, then 5 `kipptaf` edits that read the
new columns instead of deriving them. One derivation goes the other way:
`agg_credittype` has a single consumer, so it moves down into that report rather
than up into the package. The package and `kipptaf` halves ship as 2 PRs,
because a column added at package staging does not reach a `kipptaf` union
wrapper until the district projects rebuild prod.

**Tech Stack:** dbt 1.9 on BigQuery, `dbt_utils`, Dagster+ for materialization,
dbt Cloud CI. Run everything through `uv run`.

**Spec:**
[docs/superpowers/specs/2026-09-21-miami-powerschool-pushdown-design.md](../specs/2026-09-21-miami-powerschool-pushdown-design.md)

## Global Constraints

- **The design test.** A derivation is pushable only when every one of its
  inputs is frozen. A join to live data stays in `kipptaf`.
- **The refactor is value-preserving by construction.** Any row-count or value
  difference against prod is a defect, not an expected delta. The 2 deliberate
  exceptions are the 3 rows the deleted pre-2000 filter stops removing, and the
  3 new orphans they create on `dim_school_calendars.date_key`.
- **Worktree.**
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown`,
  branch `cbini/refactor/claude-miami-powerschool-pushdown`. Every `git` call is
  `git -C <worktree>`; every path is absolute under the worktree.
- **dbt invocation.**
  `uv run dbt <cmd> --project-dir <worktree>/src/dbt/<project>`. Never bare
  `dbt`. A fresh worktree has no `dbt_packages/` — run
  `uv run dbt deps --project-dir <worktree>/src/dbt/<project>` once per project,
  in its own Bash call, before the first compile.
- **Who runs what.** Claude runs `dbt compile`, `dbt parse`, and `--target dev`
  builds. `--target staging` builds are shared writes and need the user's
  authorization restated in plain text in the message immediately before the
  call, in a Bash call of its own. `--target prod` runs and every warehouse
  DML/DDL go to the user.
- **Deferral.** Every `--target dev` build below needs `--defer` against a prod
  manifest, or dbt tries to build the model's whole upstream graph into your
  `zz_<user>_*` schema. A fresh worktree has no prod manifest — invoke the
  `dbt-local-dev` skill to download it before the first dev build, and use the
  `--state` path it gives you. The dev-build steps write
  `--defer --state <prod-manifest-dir>`; substitute that path.
- **Commit messages.** The pre-commit hook can reject a `-m` message. Write each
  one to
  `/tmp/claude-1000/-workspaces-teamster/bd9168a0-4ef5-4fb1-afa3-b8d5103eb6be/scratchpad/commit-msg-<slug>.txt`
  and use `git commit -F <that path>`. One file per commit; never a shared fixed
  name. Every message ends with `Refs #5413` and
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.
- **Schema placeholders.** `zz_<user>_<project>_<schema>` is your personal dev
  schema, `<user>` being your `GITHUB_USER`. `dbt_cloud_pr_<job>_<pr>_<schema>`
  is the CI schema: `<pr>` is the pull-request number, and `<job>` is the dbt
  Cloud CI job definition id, read from `mcp__dbt__get_job_run_details(run_id)`,
  step name
  `"Create profile from connection BigQuery (override schema to '...')"`.
- **`agg_credittype` values.** The bucket is `ENG` / `MATH` / `SCI` / `SOC` by
  `like '<prefix>%'` on `credit_type`, else `credit_type` unchanged.
  Byte-for-byte the same CASE that
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__storedgrades.sql`
  runs today. It moves down to its one consumer rather than up into the package
  — Task 1 has the reasoning. Do not "fix" its case-sensitivity while moving it:
  that changes values, and this plan changes none.
- **`academic_year` = `yearid + 1990`.** Verified equal on all 126,319
  non-null-`yearid` rows of `int_powerschool__calendar_day` across all 4
  districts, zero disagreements.
- **Lint before every push.**
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree. `--force` is required or committed files are
  skipped.
- **SQL conventions** in `.claude/rules/dbt-sql.md` bind every edit: sqlfluff
  ST06 column order, no `QUALIFY`, no lateral column aliases, no subqueries, no
  `ORDER BY`, max 1 level of function nesting, enumerate columns in UNION
  branches.
- **YAML conventions** in `.claude/rules/dbt-yaml.md` bind every properties
  edit: every new column needs a `description:`, columns carrying per-column
  `data_tests:` sort to the top of the `columns:` list, model-level composite
  tests go in a `data_tests:` block above `columns:`.

---

## PR 1 — package changes and the archive re-bake

### Task 1: move `agg_credittype` into its only consumer

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__award_ceremony_gpa.sql:1-28`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__storedgrades.sql:17-38`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__storedgrades.yml:145`

**Interfaces:**

- Consumes: `credit_type` (string), already on `stg_powerschool__storedgrades`
  today.
- Produces: nothing new. `agg_credittype` stops existing as a column; the value
  is computed inline in the one report that reads it, under its existing local
  name `credittype`.

**This task touches no package file and has no cross-project dependency.** It
ships in PR 1 only because PR 1 comes first — it would be equally correct
standing alone. `credit_type` is already on the wrapper, so nothing waits on a
district rebuild.

**Why this instead of pushing it down to the package.** The spec has
`agg_credittype` moving into `stg_powerschool__storedgrades` in the package.
That is wrong, for two reasons found while planning.

The first is mechanical. The wrapper is
`select u.*, <case> as agg_credittype from union_relations as u`. Once the
package emits `agg_credittype`, `u.*` carries it and the wrapper's alias
duplicates it, so BigQuery fails with `Duplicate column name`. Drop the alias
any earlier and the column does not exist until the districts rebuild. No ship
order avoids both, so the pushdown costs a broken deploy window that no other
change in this plan costs.

The second is the stronger one. The CASE is not a canonical subject mapping; it
is a report-local heuristic that only half works. `like` is case-sensitive in
BigQuery, so it buckets `ENG-T1` and `MATH-T2` but misses `Eng`, `ELA`, `Math`,
`MaTH`, `Math-T1`, `MA` and `MAT`, all of which are live values in `credit_type`
today. A partial heuristic does not belong in a shared source package where 4
districts inherit it and other models may start trusting it. It belongs next to
the one report that accepts its limits.

`grep -rn agg_credittype src/` returns exactly 3 hits, verified 2026-09-21: the
definition, its properties entry, and `rpt_gsheets__award_ceremony_gpa.sql:12`.
No Cube view, no exposure, no Python. Moving it is contained.

- [ ] **Step 1: Compute the bucket inside the report**

In `rpt_gsheets__award_ceremony_gpa.sql`, the `grade_source` CTE's Stored branch
currently reads `sg.agg_credittype as credittype`. Replace that plain ref with
the CASE **in place**, keeping it in the same 7th slot:

```sql
    grade_source as (
        select
            'Stored' as gpa_type,

            co.school_abbreviation,
            co.grade_level,
            co.student_number,
            co.lastfirst,

            sg.course_number,

            case
                when sg.credit_type like 'ENG%'
                then 'ENG'
                when sg.credit_type like 'MATH%'
                then 'MATH'
                when sg.credit_type like 'SCI%'
                then 'SCI'
                when sg.credit_type like 'SOC%'
                then 'SOC'
                else sg.credit_type
            end as credittype,

            sg.potentialcrhrs,

            sg.earnedcrhrs,
            sg.gpa_points,

        from {{ ref("stg_powerschool__storedgrades") }} as sg
```

Everything from `inner join` onward is unchanged. Keep the `sg.` prefix: this
SELECT reads two relations, so the single-relation no-prefix rule does not
apply.

**Do not sort the CASE to the end of the select list.** sqlfluff ST06 would
normally put a case statement after every plain ref, and that is wrong here.
`grade_source` feeds a positional `union all`, and `credittype` sits at ordinal
7 in BOTH branches. Sorting it to position 10 binds the Stored branch's
`credittype` to the Live branch's `gpa_points` — a cross-type misalignment that
compiles clean and corrupts the sheet. ST06 does not fire here in any case:
sqlfluff skips the rule near the templated `{{ ref() }}` slice, and a
`trunk-ignore` for it is reported as unneeded.

Confirm the alignment before finishing. Both branches must read, in order:
`gpa_type`, `school_abbreviation`, `grade_level`, `student_number`, `lastfirst`,
`course_number`, `credittype`, `potentialcrhrs`, `earnedcrhrs`, `gpa_points`.

- [ ] **Step 2: Drop the derivation from the wrapper**

`src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__storedgrades.sql`
becomes:

```sql
select
    u.*,

    if(l.location_name is null, true, false) as is_transfer_grade,

    {{ extract_source_project("u") }} as _dbt_source_project,

from union_relations as u
left join
    {{ ref("int_people__location_crosswalk") }} as l on u.schoolname = l.location_name
```

`is_transfer_grade` stays. It reads a LEFT JOIN to a live `kipptaf` view, so it
is not row-local and has nowhere else to go.

- [ ] **Step 3: Drop the properties entry**

Remove the `agg_credittype` block at
`src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__storedgrades.yml:145`.
The column no longer exists on the model, and a properties entry for a column
the model does not produce is a parse warning at best and a contract failure
where contracts are enforced.

- [ ] **Step 4: Confirm nothing else referenced it**

```bash
grep -rn "agg_credittype" /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/
```

Expected: no output. A hit means a consumer this plan did not account for — stop
and report it rather than deleting the reference.

- [ ] **Step 5: Compile the report**

```bash
uv run dbt compile --select rpt_gsheets__award_ceremony_gpa --target staging --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kipptaf 2>&1 | tail -n 10
```

Expected: clean. `Name credit_type not found` would mean the wrapper does not
expose it, which would contradict the current schema — re-check before working
around it.

- [ ] **Step 6: Prove the report's output is unchanged**

This runs after CI builds the model. The move is value-preserving: the same CASE
over the same column, one layer later.

```sql
select count(*) as n_differing_rows,
from `teamster-332318`.dbt_cloud_pr_<job>_<pr>_kipptaf_extracts.rpt_gsheets__award_ceremony_gpa as new
full join `teamster-332318`.kipptaf_extracts.rpt_gsheets__award_ceremony_gpa as old
  on new.student_number = old.student_number
  and new.credittype = old.credittype
  and new.gpa_type = old.gpa_type
where
  to_json_string(new) != to_json_string(old)
  or new.student_number is null
  or old.student_number is null
```

Expected: 0. Confirm the join keys above are actually the report's grain before
trusting the result — read the model's tail, which groups in a `calculations`
CTE, and use whatever it groups by.

- [ ] **Step 7: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__award_ceremony_gpa.sql src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__storedgrades.sql src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__storedgrades.yml </dev/null 2>&1 | tail -n 20
```

Expected: `✔ No issues`. ST06 on the moved CASE is the likely failure; if it
fires, move the block rather than suppressing it.

- [ ] **Step 8: Commit**

Subject:
`refactor(kipptaf): compute the subject bucket in the report that uses it`.
Body: say it has one consumer, that the CASE is a case-sensitive partial
heuristic rather than a canonical mapping, and that this is why it did not go
into the package as the spec first proposed.

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown add -u
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown commit -F /tmp/claude-1000/-workspaces-teamster/bd9168a0-4ef5-4fb1-afa3-b8d5103eb6be/scratchpad/commit-msg-agg-credittype.txt
```

---

### Task 2: `academic_year` on `int_powerschool__gpa_term`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_term.sql:117-138`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_term.yml`

**Interfaces:**

- Consumes: `yearid` (int64) on `grade_rollup`.
- Produces: `academic_year` (int64) on `int_powerschool__gpa_term`. Task 4's
  `int_powerschool__gpa` reads it; Task 7's `int_students__gpa` reads it through
  that model.

This is a consistency fix, not a new pattern. `int_powerschool__ada`,
`int_powerschool__calendar_week`, `base_powerschool__final_grades` and
`int_powerschool__terms` already carry both `yearid` and `academic_year`.

- [ ] **Step 1: Derive the column in the `gpa_calcs` CTE**

Derive it upstream rather than in the final SELECT: the final SELECT is
alias-prefixed and ST06-ordered across plain refs, `round()` calls and window
functions, and an arithmetic expression has no clean home in it.
`.claude/rules/dbt-sql.md` names "derive the expression as a named column in an
upstream CTE" as the standard remedy.

In `gpa_calcs`, add the arithmetic ahead of the existing `round()` calls:

```sql
    gpa_calcs as (
        select
            *,

            yearid + 1990 as academic_year,

            round(
                safe_divide(weighted_gpa_points_term, total_credit_hours_term), 2
            ) as gpa_term,
```

- [ ] **Step 2: Project it in the final SELECT**

Add to the plain-ref block of the final SELECT, next to `gc.yearid`:

```sql
    gc.yearid,
    gc.academic_year,
```

- [ ] **Step 3: Document the column**

In
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa_term.yml`,
next to the existing `yearid` entry:

```yaml
- name: academic_year
  data_type: int64
  description:
    Academic year the term falls in, as the calendar year the year started.
    PowerSchool's yearid plus 1990.
```

- [ ] **Step 4: Build into dev**

```bash
uv run dbt build --select int_powerschool__gpa_term --target dev --defer --state <prod-manifest-dir> --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippnewark 2>&1 | tail -n 20
```

Expected: PASS.

- [ ] **Step 5: Verify the values on the dev relation**

Query the relation Step 4 just built, not prod — prod has no `academic_year`
column yet, so this query cannot run there.

```sql
select
  countif(academic_year != yearid + 1990) as n_disagree,
  countif(academic_year is null) as n_null,
  count(*) as n_rows,
from `teamster-332318`.zz_<user>_kippnewark_powerschool.int_powerschool__gpa_term
```

Expected: `n_disagree = 0`. `n_null` should equal the count of rows with a null
`yearid`; a surprise there means the arithmetic landed on rows it should not
have.

- [ ] **Step 6: Lint and commit**

Lint both files, then commit with subject
`refactor(dbt): carry academic_year on int_powerschool__gpa_term`.

---

### Task 3: `academic_year` on `int_powerschool__attendance_streak`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__attendance_streak.sql`
  (final SELECT)
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__attendance_streak.yml`

**Interfaces:**

- Consumes: `yearid` (int64) on `streaks_agg`.
- Produces: `academic_year` (int64) on `int_powerschool__attendance_streak`.
  Task 9's `int_students__attendance_streak` reads it.

- [ ] **Step 1: Add the column to the final SELECT**

The final SELECT is:

```sql
select
    *, date_diff(streak_end_date, streak_start_date, day) + 1 as streak_length_calendar,
from streaks_agg
```

Becomes:

```sql
select
    *,

    yearid + 1990 as academic_year,

    date_diff(streak_end_date, streak_start_date, day) + 1 as streak_length_calendar,
from streaks_agg
```

Arithmetic before the function call keeps ST06 happy. `sqlfmt` may rejoin the
lines; let the pre-commit hook apply that.

- [ ] **Step 2: Document the column**

```yaml
- name: academic_year
  data_type: int64
  description:
    Academic year the streak falls in, as the calendar year the year started.
    PowerSchool's yearid plus 1990.
```

- [ ] **Step 3: Build into dev and verify**

```bash
uv run dbt build --select int_powerschool__attendance_streak --target dev --defer --state <prod-manifest-dir> --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippnewark 2>&1 | tail -n 20
```

Expected: PASS, and `countif(academic_year != yearid + 1990) = 0` on the dev
relation.

- [ ] **Step 4: Lint and commit**

Subject:
`refactor(dbt): carry academic_year on int_powerschool__attendance_streak`.

---

### Task 4: `is_in_session` and `is_in_membership` on `int_powerschool__calendar_day`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__calendar_day.sql:1-10`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__calendar_day.yml`

**Interfaces:**

- Consumes: `insession` (int64) and `membershipvalue` (float64), both arriving
  through `cd.*` from `stg_powerschool__calendar_day`.
- Produces: `is_in_session` (boolean) and `is_in_membership` (boolean) on
  `int_powerschool__calendar_day`. Task 8's `int_students__calendar_day` reads
  both.

`academic_year` is NOT part of this task. `int_powerschool__calendar_day`
already carries it, and `int_students__calendar_day` already ignores it and
recomputes `yearid + 1990`. That one is free — no package change and no re-bake.
Task 8 fixes the read side.

- [ ] **Step 1: Add both booleans to the SELECT**

The model is a single SELECT. Append after the plain refs — ST06 puts logicals
(bucket 5) after column enumerations (bucket 1):

```sql
select
    cd.*,

    t.yearid,
    t.academic_year,

    sch.name as school_name,
    sch.abbreviation as school_abbreviation,
    sch.school_level,
    sch.schoolcity,

    cd.insession = 1 as is_in_session,
    cd.membershipvalue > 0 as is_in_membership,
from {{ ref("stg_powerschool__calendar_day") }} as cd
```

The rest of the model is unchanged.

- [ ] **Step 2: Document both columns**

```yaml
- name: is_in_session
  data_type: boolean
  description: True when the school is in session on this date.
- name: is_in_membership
  data_type: boolean
  description:
    True when this date counts toward student membership at this school.
```

- [ ] **Step 3: Build into dev**

```bash
uv run dbt build --select int_powerschool__calendar_day --target dev --defer --state <prod-manifest-dir> --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippnewark 2>&1 | tail -n 20
```

Expected: PASS. The model carries a `unique` test on `id` and a warn-severity
`dbt_utils.expression_is_true` on `academic_year is not null or insession != 1`;
neither should change.

- [ ] **Step 4: Verify the booleans against their sources**

```sql
select
  countif(is_in_session != (insession = 1)) as n_session_disagree,
  countif(is_in_membership != (membershipvalue > 0)) as n_membership_disagree,
  countif(is_in_session is null) as n_session_null,
  count(*) as n_rows,
from `teamster-332318`.zz_<user>_kippnewark_powerschool.int_powerschool__calendar_day
```

Expected: both disagree counts 0. `n_session_null` should be 0 too — `insession`
is not nullable in this source; if it is non-zero, the comparison is producing
NULL and `int_students__calendar_day` gets a 3-valued boolean where it had a
2-valued one.

- [ ] **Step 5: Lint and commit**

Subject:
`refactor(dbt): carry the in-session and membership flags on int_powerschool__calendar_day`.

---

### Task 5: the new `int_powerschool__gpa` package model

**Files:**

- Create: `src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa.yml`
  — holds both the `unit_tests:` block from Step 1 and the `models:` block from
  Step 5

The unit test goes in the model's own properties file, which is this repo's
dominant convention (every `unit_tests:` block in `kipptaf` sits in
`<layer>/properties/<model>.yml`). It does NOT go under
`src/dbt/powerschool/tests/` — that directory holds singular SQL tests, and dbt
only discovers `unit_tests:` in YAML under `models/`.

**Interfaces:**

- Consumes: `int_powerschool__gpa_term` (including the `academic_year` Task 2
  adds) and `int_powerschool__gpa_cumulative`.
- Produces: `int_powerschool__gpa` with 21 columns at grain
  `(studentid, schoolid, yearid, term_name)`: `studentid`, `schoolid`, `yearid`,
  `academic_year`, `term_name`, `semester`, `gpa_term`, `gpa_y1`,
  `gpa_y1_unweighted`, `gpa_semester`, `n_failing_y1`,
  `total_credit_hours_term`, `total_credit_hours_y1`, `grade_avg_term`,
  `grade_avg_y1`, `students_student_number`, `cumulative_y1_gpa`,
  `cumulative_y1_gpa_unweighted`, `cumulative_y1_gpa_projected`,
  `earned_credits_cum`, `potential_credits_cum`.

**Why a new model and not a wider `int_powerschool__gpa_term`.** Widening is the
smaller diff and it is wrong. `int_powerschool__gpa_term` feeds
`int_powerschool__gpa_term_current`, which feeds
`snapshot_powerschool__gpa_term`. A snapshot on the `check` strategy backfills
only the rows it touches, so added columns sit about 99% null. The model also
has roughly 19 other consumers.

**The join cannot fan out.** `int_powerschool__gpa_cumulative` carries an
error-severity `dbt_utils.unique_combination_of_columns` on
`(studentid, schoolid)`, which is exactly the join key. The LEFT JOIN therefore
matches at most one row, and the output grain equals
`int_powerschool__gpa_term`'s.

**The grain is verified.** `(studentid, schoolid, yearid, term_name)` is unique
on `int_powerschool__gpa_term` in all 4 district projects, measured 2026-09-21:
Newark 172,804 rows / 172,804 keys, Camden 47,732 / 47,732, Miami 16,512 /
16,512, Paterson 2,548 / 2,548. Zero collisions anywhere.

**No `_dbt_source_project` here.** The kipptaf model joins on it today; that
column is created by the kipptaf union wrapper and does not exist inside a
district project, where there is exactly one project by definition. Dropping the
predicate is correct, not a loosening.

- [ ] **Step 1: Write the failing unit test**

Use `format: sql` inputs, not dict fixtures. `int_powerschool__gpa_term` gains
`academic_year` in this same PR, and a dict fixture introspects the deferred
old-schema relation and rejects the new column (`.claude/rules/dbt-yaml.md`,
_dbt unit-test fixtures_).

```yaml
unit_tests:
  - name: int_powerschool__gpa__joins_cumulative
    description:
      One term row joins its student's single cumulative row, and a term row
      with no cumulative match survives with null cumulative measures.
    model: int_powerschool__gpa
    given:
      - input: ref('int_powerschool__gpa_term')
        format: sql
        rows: |
          select
            1 as studentid, 100 as schoolid, 35 as yearid, 2025 as academic_year,
            'Q1' as term_name, 'S1' as semester,
            3.5 as gpa_term, 3.4 as gpa_y1, 3.3 as gpa_y1_unweighted,
            3.45 as gpa_semester, 0 as n_failing_y1,
            5.0 as total_credit_hours_term, 5.0 as total_credit_hours_y1,
            90 as grade_avg_term, 89 as grade_avg_y1,
            8400001 as students_student_number
          union all
          select
            2, 100, 35, 2025, 'Q1', 'S1',
            2.0, 2.0, 2.0, 2.0, 1, 5.0, 5.0, 70, 70, 8400002
      - input: ref('int_powerschool__gpa_cumulative')
        format: sql
        rows: |
          select
            1 as studentid, 100 as schoolid,
            3.2 as cumulative_y1_gpa,
            3.1 as cumulative_y1_gpa_unweighted,
            3.3 as cumulative_y1_gpa_projected,
            20.0 as earned_credits_cum,
            22.0 as potential_credits_cum
    expect:
      rows:
        - studentid: 1
          schoolid: 100
          yearid: 35
          academic_year: 2025
          term_name: Q1
          semester: S1
          gpa_term: 3.5
          gpa_y1: 3.4
          gpa_y1_unweighted: 3.3
          gpa_semester: 3.45
          n_failing_y1: 0
          total_credit_hours_term: 5.0
          total_credit_hours_y1: 5.0
          grade_avg_term: 90
          grade_avg_y1: 89
          students_student_number: 8400001
          cumulative_y1_gpa: 3.2
          cumulative_y1_gpa_unweighted: 3.1
          cumulative_y1_gpa_projected: 3.3
          earned_credits_cum: 20.0
          potential_credits_cum: 22.0
        - studentid: 2
          schoolid: 100
          yearid: 35
          academic_year: 2025
          term_name: Q1
          semester: S1
          gpa_term: 2.0
          gpa_y1: 2.0
          gpa_y1_unweighted: 2.0
          gpa_semester: 2.0
          n_failing_y1: 1
          total_credit_hours_term: 5.0
          total_credit_hours_y1: 5.0
          grade_avg_term: 70
          grade_avg_y1: 70
          students_student_number: 8400002
          cumulative_y1_gpa: null
          cumulative_y1_gpa_unweighted: null
          cumulative_y1_gpa_projected: null
          earned_credits_cum: null
          potential_credits_cum: null
```

The second row is the point of the test: it proves the join is LEFT, so a term
row without a cumulative row survives with nulls rather than disappearing.

- [ ] **Step 2: Run it to confirm it fails**

```bash
uv run dbt test --select int_powerschool__gpa__joins_cumulative --target dev --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippnewark 2>&1 | tail -n 20
```

Expected: FAIL with a parse or compilation error naming `int_powerschool__gpa` —
the model does not exist yet.

- [ ] **Step 3: Write the model**

`src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa.sql`:

```sql
select
    gt.studentid,
    gt.schoolid,
    gt.yearid,
    gt.academic_year,
    gt.term_name,
    gt.semester,
    gt.gpa_term,
    gt.gpa_y1,
    gt.gpa_y1_unweighted,
    gt.gpa_semester,
    gt.n_failing_y1,
    gt.total_credit_hours_term,
    gt.total_credit_hours_y1,
    gt.grade_avg_term,
    gt.grade_avg_y1,
    gt.students_student_number,

    gc.cumulative_y1_gpa,
    gc.cumulative_y1_gpa_unweighted,
    gc.cumulative_y1_gpa_projected,
    gc.earned_credits_cum,
    gc.potential_credits_cum,
from {{ ref("int_powerschool__gpa_term") }} as gt
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on gt.studentid = gc.studentid
    and gt.schoolid = gc.schoolid
```

All 21 columns are plain refs grouped by source table in join order with a blank
line between the groups, which is exactly ST06 bucket 1. Nothing else is
computed here.

- [ ] **Step 4: Run the unit test to confirm it passes**

```bash
uv run dbt test --select int_powerschool__gpa__joins_cumulative --target dev --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippnewark 2>&1 | tail -n 20
```

Expected: `PASS=1`.

- [ ] **Step 5: Add the `models:` block with the grain test**

Add this below the `unit_tests:` block already in
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__gpa.yml`.
The model-level composite test goes above `columns:`; the one column carrying a
per-column test sorts to the top of the list.

```yaml
models:
  - name: int_powerschool__gpa
    description: >-
      Term-grained GPA joined to the student's cumulative GPA, so a consumer
      reads one row per student, school, year and term without joining the two
      GPA models itself. The cumulative measures repeat across a student's term
      rows — they are cumulative to date, not per term.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - studentid
              - schoolid
              - yearid
              - term_name
    columns:
      - name: students_student_number
        data_type: int64
        description: The school-facing student number.
        config:
          meta:
            contains_pii: true
      - name: studentid
        data_type: int64
        description: Internal PowerSchool student id.
      - name: schoolid
        data_type: int64
        description: PowerSchool school number.
      - name: yearid
        data_type: int64
        description:
          PowerSchool's year id, which is the academic year minus 1990.
      - name: academic_year
        data_type: int64
        description:
          Academic year the term falls in, as the calendar year the year
          started.
      - name: term_name
        data_type: string
        description: Store code for the term, such as Q1 or Y1.
      - name: semester
        data_type: string
        description:
          Semester the term rolls up to — S1 for Q1 and Q2, S2 for Q3 and Q4.
      - name: gpa_term
        data_type: float64
        description: Credit-weighted GPA for this term alone.
      - name: gpa_y1
        data_type: float64
        description: Credit-weighted year-to-date GPA as of this term.
      - name: gpa_y1_unweighted
        data_type: float64
        description: Unweighted year-to-date GPA as of this term.
      - name: gpa_semester
        data_type: float64
        description: Credit-weighted GPA across the terms in this semester.
      - name: n_failing_y1
        data_type: int64
        description: Count of year-to-date course grades starting with F.
      - name: total_credit_hours_term
        data_type: float64
        description: Credit hours behind this term's GPA.
      - name: total_credit_hours_y1
        data_type: float64
        description: Credit hours behind the year-to-date GPA.
      - name: grade_avg_term
        data_type: float64
        description:
          Mean percent grade across this term's courses, rounded to a whole
          number.
      - name: grade_avg_y1
        data_type: float64
        description: Mean year-to-date percent grade, rounded to a whole number.
      - name: cumulative_y1_gpa
        data_type: float64
        description:
          Credit-weighted GPA across every stored year, cumulative to date.
      - name: cumulative_y1_gpa_unweighted
        data_type: float64
        description:
          Unweighted GPA across every stored year, cumulative to date.
      - name: cumulative_y1_gpa_projected
        data_type: float64
        description:
          Cumulative credit-weighted GPA projected to year end, including
          in-progress courses.
      - name: earned_credits_cum
        data_type: float64
        description: Credits earned across every stored year.
      - name: potential_credits_cum
        data_type: float64
        description: Credits attempted across every stored year.
```

`students_student_number` carries `contains_pii: true` because it is the
school-facing student number — a direct identifier under 34 CFR §99.3(d). The
GPA measures are student-level education content, which
`.claude/rules/ferpa-pii.md` puts in tier 3. The existing
`int_powerschool__gpa_term` and `int_powerschool__gpa_cumulative` properties tag
only `students_student_number`, so this file follows their precedent rather than
widening the tagging; the rule says widen opportunistically, not sweep.

- [ ] **Step 6: Build and check the grain against prod**

```bash
uv run dbt build --select int_powerschool__gpa --target dev --defer --state <prod-manifest-dir> --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippnewark 2>&1 | tail -n 20
```

Expected: PASS, including the grain test. Then confirm the row count equals
`int_powerschool__gpa_term`'s, which is what a non-fanning LEFT JOIN must give:

```sql
select
  (select count(*) from `teamster-332318`.zz_<user>_kippnewark_powerschool.int_powerschool__gpa) as n_gpa,
  (select count(*) from `teamster-332318`.kippnewark_powerschool.int_powerschool__gpa_term) as n_term
```

Expected: equal, at 172,804.

- [ ] **Step 7: Lint and commit**

Subject: `feat(dbt): join term and cumulative GPA in the powerschool package`.

---

### Task 6: open PR 1

**Files:** none — this task is git and GitHub only.

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown push -u origin cbini/refactor/claude-miami-powerschool-pushdown
```

- [ ] **Step 2: Open the PR**

Use `mcp__github__create_pull_request` with the body built from
`.github/pull_request_template.md`. Keep every template line and answer its
prompts in place. Include `Refs #5413` so the PR lands on the project board;
never `gh project item-add` a PR. End the body with the
`🤖 Generated with [Claude Code]` line.

Say in the body that this PR is the package half of a 2-PR change and that the
kipptaf half follows once Dagster materializes these models in prod. Note that
Task 1 is the one kipptaf change riding along: it has no cross-project
dependency, so it does not have to wait.

- [ ] **Step 3: Verify the PR body landed as intended**

Read it back with `mcp__github__pull_request_read`. A malformed parameter
succeeds with the wrong payload.

- [ ] **Step 4: Work CI**

Invoke `pr-ci-review` for CI triage and `superpowers:receiving-code-review`
before processing any `claude-review` findings. Post a per-finding verdict as a
PR comment, and lead that comment with `@claude` or the reviewer never reads it.

Expect CI noise unrelated to this change: `state:modified+` pulls in models CI
has never built, and a 56-file sweep once surfaced 5 duplicate PKs already
sitting in prod. Query prod for the same count before assuming this PR caused a
failure.

- [ ] **Step 5: Hand the merge to the user**

Squash merge. Do not push to `main`.

---

### Task 7: the Miami archive re-bake

**Files:**

- Modify: `src/dbt/kippmiami/packages.yml` (re-include the `powerschool`
  package)
- Modify: `src/dbt/kippmiami/dbt_project.yml` (the `powerschool:` block with the
  archive post-hooks)
- Modify: `src/dbt/kippmiami/CLAUDE.md` (record the fifth rebuild)

**Interfaces:**

- Consumes: the merged PR 1 package models.
- Produces: the `kippmiami_powerschool` dataset, grown from 14 tables to 15 and
  with the 4 widened tables rebuilt. Task 8's `sources-kippmiami.yml` entry
  depends on the 15th table existing.

**This task writes to prod. The user runs the build.** The BigQuery MCP is
SELECT-only, `bq` credentials expire mid-session, and a `--target prod` dbt run
goes to the user.

**The recipe is a replay, not a fresh design.** `git show 59c7e63bcd` is the
fourth rebuild's re-include diff — the `powerschool:` block with the 16
post-hooks: the 8400 Focus prefix on `student_number`
(`stg_powerschool__students`), 14 staging models dropping rows past AY2025
(`yearid > 35`), and `stg_powerschool__calendar_day` deleting
`date_value >= '2026-07-01'`. `git show 64ff886137` is the removal that follows.
The archive has absorbed a brand-new model before (#5260), which is the evidence
that adding a 15th costs nothing beyond the bake.

**The ODBC variant, not dlt.** The archive bakes through `staging/odbc/`. That
is why Task 1 edits both — a column added to `dlt/` alone reaches the 3 NJ
districts and silently misses Miami.

- [ ] **Step 1: Replay the re-include**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown show 59c7e63bcd
```

Apply the same `packages.yml` and `dbt_project.yml` changes. Do not hand-write
the post-hook block — copy it from that commit.

- [ ] **Step 2: Check for a duplicated top-level key**

Git merges two `models: <package>:` additions at different positions with no
conflict marker, keeping both. After editing `dbt_project.yml`:

```bash
grep -n "^  powerschool:" /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippmiami/dbt_project.yml
```

Expected: exactly 1 match.

- [ ] **Step 3: Install deps and parse**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippmiami
```

Then, in its own call:

```bash
uv run dbt parse --no-partial-parse --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippmiami 2>&1 | tail -n 15
```

Expected: no errors, and the `powerschool` package models now resolve.

- [ ] **Step 4: Hand the prod build to the user**

Give them the command and say plainly that it writes the `kippmiami_powerschool`
dataset:

```bash
uv run dbt build --select package:powerschool --target prod --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kippmiami
```

Do not run it. Do not retry it if it is denied.

- [ ] **Step 5: Verify the archive after the user reports the build finished**

```sql
select table_id, row_count, timestamp_millis(last_modified_time) as modified_at,
from `teamster-332318`.kippmiami_powerschool.__TABLES__
order by table_id
```

Expected: 15 rows, `int_powerschool__gpa` present, and `modified_at` fresh on
`int_powerschool__gpa`, `int_powerschool__gpa_term`,
`int_powerschool__attendance_streak`, `int_powerschool__calendar_day` and
`stg_powerschool__storedgrades`.

`__TABLES__.row_count` lags and can read 0 on a just-built table — confirm
population with `count(*)`, not `row_count`.

Then confirm the AY2025 bound held:

```sql
select max(academic_year) as max_year, count(*) as n_rows,
from `teamster-332318`.kippmiami_powerschool.int_powerschool__gpa
```

Expected: `max_year` at or below 2025. A higher value means a post-hook did not
fire.

- [ ] **Step 6: Remove the package again**

Replay `git show 64ff886137`. The package is re-included for each rebuild and
removed after; leaving it in place makes every later Miami run try to build
PowerSchool models against frozen externals.

- [ ] **Step 7: Record the rebuild in the district CLAUDE.md**

`src/dbt/kippmiami/CLAUDE.md:15-30` narrates each rebuild. Add the fifth: it
added `int_powerschool__gpa` and widened storedgrades, the 2 GPA models,
attendance streak and calendar day, for #5413. Keep the sentence short and in
the existing voice.

- [ ] **Step 8: Commit and open the rebuild PR**

Two commits, matching the existing history's shape: one
`chore(kippmiami): re-include the powerschool package for the fifth archive rebuild`
and one
`chore(kippmiami): remove the powerschool package after the fifth archive rebuild`.

A PR touching only a district project gets a no-op kipptaf CI run — kipptaf CI
green is not evidence the district changes are correct. Step 5's queries are the
evidence.

---

## PR 2 — kipptaf changes

Every task below depends on PR 1 being merged AND Dagster having materialized
the package models in all 3 NJ districts, plus the Miami re-bake from Task 7.
`dbt_utils.union_relations` resolves its column list at compile time from the
source relations' `INFORMATION_SCHEMA`, so a new package column does not exist
at a kipptaf wrapper until the district tables actually carry it.

- [ ] **Gate: confirm all 4 districts carry the new columns before starting**

```sql
select table_schema, table_name, column_name,
from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.COLUMNS
where
  table_schema in (
    'kippnewark_powerschool', 'kippcamden_powerschool',
    'kippmiami_powerschool', 'kipppaterson_powerschool'
  )
  and (
    (table_name = 'int_powerschool__gpa_term' and column_name = 'academic_year')
    or (table_name = 'int_powerschool__attendance_streak' and column_name = 'academic_year')
    or (table_name = 'int_powerschool__calendar_day' and column_name in ('is_in_session', 'is_in_membership'))
  )
order by table_schema, table_name, column_name
```

Expected: 16 rows — 4 columns × 4 districts. Anything less means a district has
not rebuilt and PR 2 will fail CI deterministically. Wait rather than working
around it.

---

### Task 8: the kipptaf `int_powerschool__gpa` union wrapper

**Files:**

- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa.sql`
- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gpa.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`

**Interfaces:**

- Consumes: `int_powerschool__gpa` in all 4 district projects.
- Produces: kipptaf `int_powerschool__gpa`, the 21 package columns plus
  `_dbt_source_relation` (from the union) and `_dbt_source_project`. Task 9's
  `int_students__gpa` reads it.

**The new wrapper is additive.** `int_powerschool__gpa_term` and
`int_powerschool__gpa_cumulative` both stay. Other models read them directly,
and `int_powerschool__gpa_cumulative` still holds the KTAF GPA bands until
[#5462](https://github.com/TEAMSchools/teamster/issues/5462) moves them.

- [ ] **Step 1: Write the wrapper**

Follow the sibling `int_powerschool__gpa_term.sql` exactly:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "int_powerschool__gpa"),
                    source("kippcamden_powerschool", "int_powerschool__gpa"),
                    source("kippmiami_powerschool", "int_powerschool__gpa"),
                    source("kipppaterson_powerschool", "int_powerschool__gpa"),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,
from union_relations as ur
```

- [ ] **Step 2: Add the Miami source entry**

In `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`, add to `tables:`:

```yaml
- name: int_powerschool__gpa
  config:
    meta:
      dagster:
        group: powerschool
        asset_key:
          - kippmiami
          - powerschool
          - int_powerschool__gpa
```

Then update the source `description:` at the top of that file: it says "14
permanent tables in total" and is now 15.

- [ ] **Step 3: Add the NJ source entries**

The 3 NJ `sources-kipp*.yml` files in the same directory need the same entry.
Check each one's existing `int_powerschool__gpa_term` block and copy its shape —
they may differ from the Miami file, which is a frozen BQ-native archive while
the NJ files are live district sources.

- [ ] **Step 4: Write the properties file**

A kipptaf-level `union_relations` view over per-region tables is functionally an
intermediate. Per `src/dbt/kipptaf/CLAUDE.md`, do NOT add a uniqueness test or
`materialized: table` — both belong on the per-region source models, and the
grain test is already on the package model from Task 5.

`config.meta.contains_pii` does not travel through `source()`, so the wrapper
must re-declare it. Model level suffices for a `select *` passthrough, whose
column docs live on the source model:

```yaml
models:
  - name: int_powerschool__gpa
    description: >-
      Network-wide union of the districts' term-grained GPA joined to cumulative
      GPA. Column semantics live on the package model.
    config:
      meta:
        contains_pii: true
```

- [ ] **Step 5: Validate the wrapper compiles with a real column list**

A dev-target compile expands to nothing — the `zz_<user>_*` dataset holds no
copy of the source relations. Use the staging target, which resolves against the
same `zz_stg_*` relations dbt Cloud CI reads and is not a warehouse write:

```bash
uv run dbt compile --select int_powerschool__gpa --target staging --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kipptaf 2>&1 | tail -n 10
```

Then read the compiled SQL at
`src/dbt/kipptaf/target/compiled/kipptaf/models/powerschool/intermediate/int_powerschool__gpa.sql`
and confirm the 21 columns are listed. An empty expansion still compiles clean,
so "no error" is not the check — reading the column list is.

- [ ] **Step 6: Lint and commit**

Subject: `feat(kipptaf): union the districts' joined GPA model`.

---

### Task 9: rewrite `int_students__gpa`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__gpa.sql:1-41`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__gpa.yml`
  (only if a column description references the join)

**Interfaces:**

- Consumes: kipptaf `int_powerschool__gpa` from Task 8.
- Produces: no change to the model's output columns. This is a pure
  substitution: the same 21 values, read instead of computed.

Only the `powerschool_conformed` CTE changes. `focus_conformed` and the
`full union all corresponding` are untouched.

- [ ] **Step 1: Replace the CTE**

```sql
    powerschool_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            schoolid,
            yearid,
            academic_year,
            term_name,
            semester,
            gpa_term,
            gpa_y1,
            gpa_y1_unweighted,
            gpa_semester,
            n_failing_y1,
            total_credit_hours_term,
            total_credit_hours_y1,
            grade_avg_term,
            grade_avg_y1,
            cumulative_y1_gpa,
            cumulative_y1_gpa_unweighted,
            cumulative_y1_gpa_projected,
            earned_credits_cum,
            potential_credits_cum,
            students_student_number as student_number,

            -- The PowerSchool GPA chain does not produce class rank at all.
            cast(null as int64) as class_rank,
        from {{ ref("int_powerschool__gpa") }}
    ),
```

3 things go away with the join: the `gt.` / `gc.` alias prefixes (this SELECT
now reads one relation, and `.claude/rules/dbt-sql.md` forbids prefixing then),
the `gt.yearid + 1990 as academic_year` derivation, and the comment explaining
it. The `class_rank` comment stays — it explains something a reader of that line
cannot see.

- [ ] **Step 2: Check the Focus branch still aligns**

`focus_conformed` must still produce the same column set, because
`full union all corresponding` matches by name. Confirm nothing was dropped:

```bash
grep -c "as " /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kipptaf/models/students/intermediate/int_students__gpa.sql
```

This is a weak check. The real one is Step 4.

- [ ] **Step 3: Compile**

```bash
uv run dbt compile --select int_students__gpa --target staging --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kipptaf 2>&1 | tail -n 10
```

Expected: clean. A missing column on either branch surfaces here as
`Name <col> not found`.

- [ ] **Step 4: Prove the rewrite is value-preserving**

This runs after CI builds the model into the PR schema. Compare the PR-branch
relation to prod on row count, key count, and every measure:

```sql
select
  (select count(*) from `teamster-332318`.dbt_cloud_pr_<job>_<pr>_kipptaf_students.int_students__gpa) as n_new,
  (select count(*) from `teamster-332318`.kipptaf_students.int_students__gpa) as n_old,
  (select count(distinct format('%T|%T|%T|%T|%T', student_number, academic_year, schoolid, term_name, _dbt_source_project))
   from `teamster-332318`.dbt_cloud_pr_<job>_<pr>_kipptaf_students.int_students__gpa) as k_new,
  (select count(distinct format('%T|%T|%T|%T|%T', student_number, academic_year, schoolid, term_name, _dbt_source_project))
   from `teamster-332318`.kipptaf_students.int_students__gpa) as k_old
```

Expected: `n_new = n_old` and `k_new = k_old`, exactly.

Then the value check, which the counts alone do not give:

```sql
select count(*) as n_differing_rows,
from `teamster-332318`.dbt_cloud_pr_<job>_<pr>_kipptaf_students.int_students__gpa as new
full join `teamster-332318`.kipptaf_students.int_students__gpa as old
  on new.student_number = old.student_number
  and new.academic_year = old.academic_year
  and new.schoolid = old.schoolid
  and new.term_name = old.term_name
  and new._dbt_source_project = old._dbt_source_project
where
  to_json_string(new) != to_json_string(old)
  or new.student_number is null
  or old.student_number is null
```

Expected: 0. A non-zero count is a defect — the refactor changes no values by
construction.

`<job>` is the dbt Cloud CI job definition id, read from
`mcp__dbt__get_job_run_details(run_id)`, step name
`"Create profile from connection BigQuery (override schema to '...')"`.

- [ ] **Step 5: Lint and commit**

Subject: `refactor(kipptaf): read the joined GPA model instead of joining it`.

---

### Task 10: rewrite `int_students__calendar_day` and clear the stale dim description

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__calendar_day.sql:10-52`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_school_calendars.yml:20-27`

**Interfaces:**

- Consumes: `is_in_session`, `is_in_membership` and `academic_year` on the
  kipptaf `int_powerschool__calendar_day` wrapper.
- Produces: the same 13 output columns as today, plus 3 more rows network-wide.

**Deleting the pre-2000 filter is deliberate and it is the only intentional
row-count change in this plan.** The filter removes exactly 3 rows — 1 Camden
and 2 Newark, and 0 Miami — so it was never a Miami pushdown item. All 3 are
PowerSchool's missing-date placeholder: `date_value` 1900-01-01, `yearid` null,
`insession` 0, `membershipvalue` 0, at 3 real high schools. They exist unchanged
in the raw external, so the fix belongs in the SIS, and it is tracked for school
ops in Asana. The workaround hides a real source error; the warn makes it
visible.

- [ ] **Step 1: Collapse the 2 PowerSchool CTEs into 1**

`powerschool_dated` and `powerschool_conformed` exist only to hold the filter
and the 3 derivations. All 3 derivations now arrive on the wrapper and the
filter is deleted, so the 2 CTEs become 1:

```sql
    powerschool_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            schoolid,
            insession,
            membershipvalue,
            week_start_date,
            week_end_date,
            date_value,
            yearid,
            is_in_session,
            is_in_membership,
            academic_year,

            date_value as school_date,
        from {{ ref("int_powerschool__calendar_day") }}
    ),
```

`date_value as school_date` is a plain ref under a second name, so it sorts with
the column enumerations; keeping it last inside that block preserves the output
order the final SELECT expects. The alias prefixes go: one relation, no
prefixes.

- [ ] **Step 2: Leave the final SELECT and the Focus branch alone**

Both branches still enumerate the same 13 columns in the same order. The comment
above the final SELECT explaining why they are enumerated stays — it is true and
a reader of that line cannot see it.

- [ ] **Step 3: Strip the stale detail from the dim description**

`dim_school_calendars.yml:22-27` currently reads:

> Each day of the school year including holidays and weekends, such as the
> school day. Indexed. Currently warns on 3 NULL rows (project-default
> `not_null` severity) — junk pre-2000 source dates sanitized to NULL upstream
> by PR #3809; the 3 rows themselves should be filtered out of this dim. See
> follow-up note in #3719 thread.

Replace with:

```yaml
description: >-
  Each day of the school year including holidays and weekends, such as the
  school day. Indexed.
```

The stale half describes a NULL-sanitizing upstream that no longer exists. Do
not replace it with a note about the 3 new orphans: a count in a description
goes stale the moment ops deletes the records. The failing rows land in the
stored-failures view, and the open item lives in Asana.

- [ ] **Step 4: Compile**

```bash
uv run dbt compile --select int_students__calendar_day --target staging --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kipptaf 2>&1 | tail -n 10
```

Expected: clean.

- [ ] **Step 5: Confirm the row-count delta is exactly 3, and that it is the 3
      expected rows**

After CI builds:

```sql
select
  (select count(*) from `teamster-332318`.dbt_cloud_pr_<job>_<pr>_kipptaf_students.int_students__calendar_day) as n_new,
  (select count(*) from `teamster-332318`.kipptaf_students.int_students__calendar_day) as n_old
```

Expected: `n_new - n_old = 3`, exactly.

```sql
select _dbt_source_project, schoolid, date_value, yearid, insession, membershipvalue,
from `teamster-332318`.dbt_cloud_pr_<job>_<pr>_kipptaf_students.int_students__calendar_day
where date_value < '2000-01-01'
```

Expected: 3 rows, all `date_value` 1900-01-01, `yearid` null, `insession` 0,
`membershipvalue` 0, 1 in Camden and 2 in Newark, 0 in Miami.

- [ ] **Step 6: Confirm the booleans did not change for every other row**

```sql
select count(*) as n_differing_rows,
from `teamster-332318`.dbt_cloud_pr_<job>_<pr>_kipptaf_students.int_students__calendar_day as new
inner join `teamster-332318`.kipptaf_students.int_students__calendar_day as old
  on new.schoolid = old.schoolid
  and new.date_value = old.date_value
  and new._dbt_source_project = old._dbt_source_project
where to_json_string(new) != to_json_string(old)
```

Expected: 0.

- [ ] **Step 7: Expect 3 new warns on `dim_school_calendars`, and leave them
      warning**

The `relationships` test on `dim_school_calendars.date_key` now finds 3 orphans:
`dim_dates` starts at exactly 2000-01-01, so the deleted filter's threshold
coincided with the dimension's lower bound. All 5 dbt projects default to
`+severity: warn` with `+store_failures_as: view`, so this needs no severity
change and the failing rows land in a view. Do not add a severity override and
do not filter the rows back out.

- [ ] **Step 8: Lint and commit**

Subject:
`refactor(kipptaf): read the calendar flags and drop the pre-2000 workaround`.

---

### Task 11: rewrite `int_students__attendance_streak`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__attendance_streak.sql:44-58`

**Interfaces:**

- Consumes: `academic_year` on the kipptaf `int_powerschool__attendance_streak`
  wrapper.
- Produces: no change to output columns or values.

- [ ] **Step 1: Read the column instead of deriving it**

The PowerSchool branch's final SELECT changes its last line:

```sql
select
    _dbt_source_relation,
    studentid,
    student_number,
    yearid,
    att_code,
    streak_id,
    streak_start_date,
    streak_end_date,
    streak_length_membership,
    streak_length_calendar,
    _dbt_source_project,
    academic_year,
from {{ ref("int_powerschool__attendance_streak") }}
```

`academic_year` moves into the plain-ref block, where the Focus branch already
has it in the same position. The 2 branches stay positionally aligned, which
`union all` requires.

- [ ] **Step 2: Keep the comment above the SELECT**

The note about the archive ending at AY2025 and needing no cutover predicate is
still true and still load-bearing. Do not delete it with the derivation.

- [ ] **Step 3: Compile**

```bash
uv run dbt compile --select int_students__attendance_streak --target staging --project-dir /workspaces/teamster/.worktrees/cbini/refactor/claude-miami-powerschool-pushdown/src/dbt/kipptaf 2>&1 | tail -n 10
```

Expected: clean.

- [ ] **Step 4: Prove it value-preserving after CI builds**

```sql
select count(*) as n_differing_rows,
from `teamster-332318`.dbt_cloud_pr_<job>_<pr>_kipptaf_students.int_students__attendance_streak as new
full join `teamster-332318`.kipptaf_students.int_students__attendance_streak as old
  on new.streak_id = old.streak_id
  and new._dbt_source_project = old._dbt_source_project
where
  to_json_string(new) != to_json_string(old)
  or new.streak_id is null
  or old.streak_id is null
```

Expected: 0.

- [ ] **Step 5: Lint and commit**

Subject: `refactor(kipptaf): read academic_year on the attendance streak union`.

---

### Task 12: open PR 2 and close out

**Files:** none beyond the PR body.

- [ ] **Step 1: Push and open the PR**

Body from `.github/pull_request_template.md`, `Refs #5413`, and the
`🤖 Generated with [Claude Code]` line. Say that this is the kipptaf half, name
PR 1, and state the one intentional behavior change: 3 more rows on
`int_students__calendar_day` and 3 new warns on `dim_school_calendars.date_key`,
both deliberate.

- [ ] **Step 2: Verify the PR body landed as intended**

Read it back with `mcp__github__pull_request_read`.

- [ ] **Step 3: Run every verification query in Tasks 9, 10 and 11**

Post the results as a PR comment. The refactor is value-preserving by
construction, so the comment's job is to show the differing-row counts are 0 and
the calendar delta is exactly 3.

- [ ] **Step 4: Work CI and review**

`pr-ci-review` for CI, `superpowers:receiving-code-review` before processing
`claude-review` findings, per-finding verdicts as a PR comment led with
`@claude`.

- [ ] **Step 5: Hand the merge to the user**

- [ ] **Step 6: Comment the outcome on #5413 and leave it to the user to close**

Say which of the audit's items shipped and which did not: the GPA band move is
[#5462](https://github.com/TEAMSchools/teamster/issues/5462) and the 3
placeholder calendar days are tracked for school ops in Asana.

---

## What this plan does not do

- **Move the KTAF GPA bands.** They stay in `int_powerschool__gpa_cumulative`
  for now. Moving them changes prod values in a model that feeds outbound
  extracts, needs no re-bake, and has a different driver. That is #5462.
- **Touch `int_students__attendance_daily`.** Its PowerSchool arm joins the
  frozen archive to `focus_stints`, drawn from
  `int_students__student_enrollment_union` filtered to Miami. Focus is the live
  SIS, so the join result keeps changing after the bake and the value cannot be
  frozen. It passes the design test.
- **Move `is_transfer_grade`.** It reads a LEFT JOIN to
  `int_people__location_crosswalk`, a live `kipptaf` view, so it is not
  row-local and has nowhere to go. Its sibling `agg_credittype` leaves the model
  in Task 1, but downward into its consumer, not up into the package.
- **Push `agg_credittype` into the `powerschool` package.** The spec proposed
  this; Task 1 explains why the plan does the opposite.
- **Add a uniqueness test to `int_powerschool__gpa_term`.** It has none, which
  the repo's per-layer requirements say every intermediate must. That is
  pre-existing debt and fixing it here would widen the blast radius of a
  refactor whose whole claim is that it changes no values. Task 5's new model
  carries the grain test the requirement asks for.
