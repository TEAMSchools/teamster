# PowerSchool Terms Quarter Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `int_students__attendance_daily` dropping 1,864,931 membership
days by giving `int_powerschool__terms` a `terms`-sourced quarter fallback and
left joining the term spine.

**Architecture:** `int_powerschool__terms` today derives quarter dates only from
`stg_powerschool__termbins`, so 94 quarters across 25 NJ school-years with no
`termbins` row produce no quarters. Add a second branch over
`stg_powerschool__terms`'s own `Q1`-`Q4` rows, anti-joined against the
`termbins` branch on `(schoolid, yearid, term)` so `termbins` stays
authoritative and no existing value changes. Then make the attendance model's
term join a `LEFT JOIN` as the backstop for the residual, and fix two inert
defects in `int_students__terms`.

**Tech Stack:** dbt on BigQuery. Source-system package `src/dbt/powerschool`
consumed by `kippnewark` / `kippcamden` / `kipppaterson`; network project
`src/dbt/kipptaf` reads the districts through `union_relations` wrappers.

## Global Constraints

- Design doc:
  `docs/superpowers/specs/2026-09-17-powerschool-terms-quarter-coverage-design.md`.
  It is approved; do not re-litigate the approach.
- Worktree:
  `/workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage`.
  Every git call is `git -C <worktree>`; every path is absolute under it.
- Branch `cbini/fix/claude-terms-quarter-coverage`, issue #5390. PR body closes
  it.
- All four changes ship in ONE PR. Change 1 is value-only — the column set of
  `int_powerschool__terms` is unchanged (`schoolid`, `yearid`, `academic_year`,
  `term`, `term_start_date`, `term_end_date`, `semester`, `is_current_term`) —
  so per `.claude/rules/dbt-models.md` no `zz_stg_*` staging dance is needed.
- No `QUALIFY`, no subqueries against tables or CTEs, no `ORDER BY`, no
  one-sided calculations in join predicates, max 1 level of function nesting.
  Column order inside every `SELECT` follows sqlfluff ST06: plain refs grouped
  by source table in join order, then constants, then simple functions, then
  logicals.
- `FULL JOIN` conditions referencing one side stay in `ON`; a row FILTER does
  not belong there at all.
- No local `dbt build` is possible: the worktree has no prod manifest, so
  `--defer --state` cannot resolve and a bare `--target dev` build reads empty
  `zz_cbini_*` schemas. Verification is a BigQuery prod-simulation query per
  change plus `dbt compile`. dbt Cloud CI does the authoritative build.
- Warehouse access is SELECT-only through the BigQuery MCP. Never write a
  `DELETE`, `DROP`, `CREATE`, `INSERT`, or `UPDATE`.
- Never put a student-level value in a commit message, PR body, or issue
  comment. Counts and aggregates are fine.

---

### Task 1: `terms`-sourced quarter fallback in the package model

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms.sql`
  (whole file, 24 lines today)
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__terms.yml`

**Interfaces:**

- Consumes: `stg_powerschool__terms` (`schoolid`, `yearid`, `academic_year`,
  `abbreviation`, `firstday`, `lastday`, `semester`, `isyearrec`, `id`) and
  `stg_powerschool__termbins` (`termid`, `schoolid`, `storecode`, `date1`,
  `date2`).
- Produces: `int_powerschool__terms` with its column set unchanged — `schoolid`
  INT64, `yearid` INT64, `academic_year` INT64, `term` STRING, `term_start_date`
  DATE, `term_end_date` DATE, `semester` STRING, `is_current_term` BOOL. Task 3
  and `int_powerschool__student_course_grades_spine` read it.

- [ ] **Step 1: Install package dependencies once for the worktree**

The worktree is fresh, so `dbt_packages/` is absent and any `dbt` command fails
on missing `dbt_utils`. Run it in its own Bash call.

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage/src/dbt/kippnewark
```

Expected: `Installing dbt-labs/dbt_utils` and the local package links, exit 0.

- [ ] **Step 2: Confirm the coverage gap against prod**

This is the failing measurement. Run via `mcp__bigquery__execute_sql`.

```sql
with
    termbins_years as (
        select distinct schoolid, yearid, _dbt_source_project,
        from `teamster-332318`.kipptaf_powerschool.int_powerschool__terms
    ),

    terms_quarter_years as (
        select distinct schoolid, yearid, _dbt_source_project,
        from `teamster-332318`.kipptaf_powerschool.stg_powerschool__terms
        where abbreviation in ('Q1', 'Q2', 'Q3', 'Q4') and schoolid != 0
    )

select
    tq._dbt_source_project,
    count(*) as school_years_with_raw_quarters,
    countif(tb.yearid is null) as school_years_missing_from_termbins,
from terms_quarter_years as tq
left join
    termbins_years as tb
    on tq.schoolid = tb.schoolid
    and tq.yearid = tb.yearid
    and tq._dbt_source_project = tb._dbt_source_project
group by tq._dbt_source_project
```

Expected: 94 uncovered quarters across 25 school-years -- `kippnewark` 65 across
17, `kippcamden` 29 across 8, `kipppaterson` none. A nonzero figure is the gap
this task closes.

- [ ] **Step 3: Rewrite the package model**

Replace the entire contents of
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms.sql` with:

```sql
with
    termbins_quarters as (
        select
            t.schoolid,
            t.yearid,
            t.academic_year,

            tb.storecode as term,
            tb.date1 as term_start_date,
            tb.date2 as term_end_date,

            if(tb.storecode in ('Q1', 'Q2'), 'S1', 'S2') as semester,
        from {{ ref("stg_powerschool__terms") }} as t
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on t.id = tb.termid
            and t.schoolid = tb.schoolid
            and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
        where t.isyearrec = 1 and t.schoolid != 0
    ),

    terms_quarters as (
        select
            t.schoolid,
            t.yearid,
            t.academic_year,
            t.semester,
            t.abbreviation as term,
            t.firstday as term_start_date,
            t.lastday as term_end_date,

            tb.term as termbins_term,
        from {{ ref("stg_powerschool__terms") }} as t
        left join
            termbins_quarters as tb
            on t.schoolid = tb.schoolid
            and t.yearid = tb.yearid
            and t.abbreviation = tb.term
        where t.abbreviation in ('Q1', 'Q2', 'Q3', 'Q4') and t.schoolid != 0
    ),

    all_quarters as (
        select
            schoolid,
            yearid,
            academic_year,
            term,
            term_start_date,
            term_end_date,
            semester,
        from termbins_quarters

        union all

        -- termbins wins wherever it carries the quarter; this branch fills only
        -- the school-years it has no rows for at all.
        select
            schoolid,
            yearid,
            academic_year,
            term,
            term_start_date,
            term_end_date,
            semester,
        from terms_quarters
        where termbins_term is null
    )

select
    schoolid,
    yearid,
    academic_year,
    term,
    term_start_date,
    term_end_date,
    semester,

    if(
        current_date('{{ var("local_timezone") }}')
        between term_start_date and term_end_date,
        true,
        false
    ) as is_current_term,
from all_quarters
```

Three notes for the reviewer, all load-bearing:

- The `termbins` branch is byte-for-byte the old model minus `is_current_term`,
  which moves to the final `SELECT` so one expression serves both branches.
- The anti-join cannot fan out: `termbins_quarters` is unique on
  `(schoolid, yearid, term)` by its own `severity: error` test.
- The fallback branch cannot fan out either. All 840 `Q1`-`Q4` rows across the
  three districts are singletons on `(schoolid, yearid, abbreviation)`, verified
  in prod 2026-09-17 (`kippnewark` 548, `kippcamden` 276, `kipppaterson` 16,
  zero duplicated keys).
- The fallback takes no `isyearrec` filter. `isyearrec = 1` selects the
  year-long record, which is what the `termbins` branch joins FROM; the quarter
  rows this branch reads are `isyearrec = 0`.

- [ ] **Step 4: Verify the rewrite against prod**

Run the new SQL body against prod relations and check both the recovery and the
uniqueness invariant.

```sql
with
    termbins_quarters as (
        select
            t.schoolid,
            t.yearid,
            t._dbt_source_project,

            tb.storecode as term,
            tb.date1 as term_start_date,
            tb.date2 as term_end_date,
        from `teamster-332318`.kipptaf_powerschool.stg_powerschool__terms as t
        inner join
            `teamster-332318`.kipptaf_powerschool.stg_powerschool__termbins as tb
            on t.id = tb.termid
            and t.schoolid = tb.schoolid
            and t._dbt_source_project = tb._dbt_source_project
            and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
        where t.isyearrec = 1 and t.schoolid != 0
    ),

    terms_quarters as (
        select
            t.schoolid,
            t.yearid,
            t._dbt_source_project,
            t.abbreviation as term,
            t.firstday as term_start_date,
            t.lastday as term_end_date,

            tb.term as termbins_term,
        from `teamster-332318`.kipptaf_powerschool.stg_powerschool__terms as t
        left join
            termbins_quarters as tb
            on t.schoolid = tb.schoolid
            and t.yearid = tb.yearid
            and t.abbreviation = tb.term
            and t._dbt_source_project = tb._dbt_source_project
        where t.abbreviation in ('Q1', 'Q2', 'Q3', 'Q4') and t.schoolid != 0
    ),

    all_quarters as (
        select schoolid, yearid, _dbt_source_project, term,
        from termbins_quarters

        union all

        select schoolid, yearid, _dbt_source_project, term,
        from terms_quarters
        where termbins_term is null
    )

select
    _dbt_source_project,
    count(*) as quarter_rows,
    count(
        distinct format('%T|%T|%T', schoolid, yearid, term)
    ) as distinct_quarter_keys,
from all_quarters
group by _dbt_source_project
```

Expected: `quarter_rows` equals `distinct_quarter_keys` for every region, which
is the `unique_combination_of_columns(schoolid, yearid, term)` test holding by
construction. `quarter_rows` exceeds today's `int_powerschool__terms` count for
`kippnewark` and `kippcamden`.

Note the prod simulation adds `_dbt_source_project` to every join and grouping
because it reads the kipptaf union wrappers, which hold all three districts in
one relation. The package model itself runs per district and needs no such
predicate.

- [ ] **Step 5: Compile the package model**

```bash
uv run dbt compile --select int_powerschool__terms --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage/src/dbt/kippnewark --target prod 2>&1 | tail -n 20
```

Expected: `Compiled node 'model.powerschool.int_powerschool__terms'` or a clean
`Concurrency` / `Done` summary with no errors. `dbt compile` performs no
warehouse write.

- [ ] **Step 6: Document the model**

The properties file carries no descriptions today. It is a modified model, so
per `.claude/rules/dbt-yaml.md` it needs one on the model and every column.
Replace the entire contents of
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__terms.yml`
with:

```yaml
models:
  - name: int_powerschool__terms
    description: >-
      One row per school, school year, and quarter, with the quarter's date
      range. Quarter dates resolve from termbins where termbins carries the
      quarter, and from the raw terms table's own Q1-Q4 record where it does
      not. Termbins is authoritative on the overlap because it is what every
      quarter in this model resolved through historically, and the two sources
      disagree on dates for a minority of quarters. The fallback branch exists
      because some school years have no termbins rows at all even though terms
      carries their quarter records.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - schoolid
              - yearid
              - term
          config:
            severity: error
    columns:
      - name: schoolid
        description: The School_Number of the school the quarter belongs to.
      - name: yearid
        description: >-
          A number representing which year the quarter belongs to (e.g. 35 for
          2025-2026).
      - name: academic_year
        description:
          Academic year the quarter falls in, the school year's starting year.
      - name: term
        description: Quarter code -- Q1, Q2, Q3, or Q4.
      - name: term_start_date
        description: >-
          First calendar date of the quarter. From termbins date1, or the terms
          record's firstday on the fallback branch.
      - name: term_end_date
        description: >-
          Last calendar date of the quarter. From termbins date2, or the terms
          record's lastday on the fallback branch.
      - name: semester
        description:
          Semester the quarter falls in -- S1 for Q1 and Q2, S2 for Q3 and Q4.
      - name: is_current_term
        description: Whether today falls within the quarter's date range.
```

- [ ] **Step 7: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__terms.yml </dev/null 2>&1 | tail -n 30
```

Expected: `✔ No issues`. On a prettier or sqlfmt complaint, run
`/workspaces/teamster/.trunk/tools/trunk fmt <files>` and re-check.

- [ ] **Step 8: Commit**

Write the commit message into your own session scratchpad first — the absolute
path is in your system prompt — as `commit-msg-terms-fallback.txt`. Write's
content is hook-scan-exempt and no hook rule covers the scratchpad, so a message
a `-m` flag would get denied for goes through. One file per commit; never a
shared path under `.claude/scratch/`, which concurrent sessions share.

Subject: `fix(dbt): fall back to terms for quarters termbins omits`. Body: the
94 uncovered quarters across 25 school-years and that termbins stays
authoritative on the overlap. End with `Refs #5390` and
`Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage add -u && git -C /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage commit -F <your scratchpad>/commit-msg-terms-fallback.txt
```

Stage with `add -u`, never `-A` — `-A` picks up unrelated files and naming a
protected path trips the hook.

---

### Task 2: left join the term spine in `int_students__attendance_daily`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__attendance_daily.sql:179-181`
  (projection) and `:239-246` (the `calcs` join)
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__attendance_daily.yml`

**Interfaces:**

- Consumes: `int_students__terms` (`yearid`, `schoolid`, `term_start_date`,
  `term_end_date`, `_dbt_source_project`, `term`, `semester`, `academic_year`)
  and the model's own `memberships` CTE (`yearid`, `schoolid`, `calendardate`,
  `_dbt_source_project`, `week_start_monday`).
- Produces: `int_students__attendance_daily` at unchanged grain
  `(student_number, _dbt_source_project, calendardate)`, with `academic_year`
  non-null on every row and `term` / `semester` nullable.

- [ ] **Step 1: Confirm the drop, and the number that replaces it**

```sql
select
    mem._dbt_source_project,
    count(*) as membership_days,
    countif(t.term is null) as days_matching_no_quarter,
from `teamster-332318`.kipptaf_students.int_students__enrollment_daily as mem
left join
    `teamster-332318`.kipptaf_students.int_students__terms as t
    on mem.yearid = t.yearid
    and mem.schoolid = t.schoolid
    and mem.calendardate between t.term_start_date and t.term_end_date
    and mem._dbt_source_project = t._dbt_source_project
    and t.term is not null
where mem.week_start_monday is not null
group by mem._dbt_source_project
```

Expected today: `days_matching_no_quarter` sums to 1,864,931 — `kippnewark`
1,139,469, `kippcamden` 232,980, `kippmiami` 492,482, `kipppaterson` 0.
`membership_days` sums to 16,035,288.

The same query re-run after Task 1 reaches prod must return 552,757 unmatched
and the SAME 16,035,288 total. An increased total means the fallback fanned out
and Task 1 is wrong.

This query reads `int_students__enrollment_daily` as the membership source
because `int_students__attendance_daily`'s own `memberships` CTE is internal to
the model and not separately queryable.

- [ ] **Step 2: Change the join to a left join**

In `int_students__attendance_daily.sql`, in the `calcs` CTE, change exactly one
word. Old:

```sql
        from memberships as mem
        inner join
            {{ ref("int_students__terms") }} as t
            on mem.yearid = t.yearid
```

New:

```sql
        from memberships as mem
        left join
            {{ ref("int_students__terms") }} as t
            on mem.yearid = t.yearid
```

Leave the four remaining `ON` predicates and `and t.term is not null` exactly as
they are. Under a `LEFT JOIN` that last predicate restricts which `t` rows may
match without dropping any `mem` row, which is what keeps the join at quarter
grain. Leave the `where mem.week_start_monday is not null` line and its comment
untouched.

- [ ] **Step 3: Make `academic_year` fall back to the membership year**

`academic_year = yearid + 1990` is the school year's starting year, verified
against every PowerSchool district and year in prod. Old, lines 179-181:

```sql
            t.academic_year,
            t.semester,
            t.term,

            abs(mem.attendancevalue - 1) as is_absent,
```

New:

```sql
            t.semester,
            t.term,

            coalesce(t.academic_year, mem.yearid + 1990) as academic_year,

            abs(mem.attendancevalue - 1) as is_absent,
```

`t.academic_year` leaves the plain-ref group and the `coalesce` joins the
simple-function group, which is what sqlfluff ST06 requires.

- [ ] **Step 4: Add the `not_null` test on `academic_year`**

Per `.claude/rules/dbt-yaml.md`, a column carrying per-column `data_tests:`
sorts to the top of the `columns:` list. Delete the existing untested entry:

```yaml
- name: academic_year
  description: Academic year from the terms join.
```

and insert this immediately after the `calendardate` entry, which is the last of
the currently-tested columns:

```yaml
- name: academic_year
  description: >-
    Academic year the day falls in, the school year's starting year. From the
    int_students__terms quarter row covering the day, falling back to the
    membership row's own yearid plus 1990 on a day no quarter covers.
  data_tests:
    - not_null:
        config:
          severity: error
```

The test is not vacuous. The rule against a `not_null` on a `coalesce` applies
to a coalesce with a non-null DEFAULT; `mem.yearid + 1990` is null whenever
`mem.yearid` is, and the old `INNER JOIN` was what hid such a row.

Also update the two sibling descriptions, which now overstate their source:

```yaml
- name: semester
  description: >-
    Reporting semester from the terms join. Null on a day no quarter covers.
- name: term
  description: >-
    Reporting term from the terms join. Null on a day no quarter covers.
```

- [ ] **Step 5: Verify the fallback covers every row**

```sql
select
    countif(t.academic_year is null) as null_from_terms,
    countif(coalesce(t.academic_year, mem.yearid + 1990) is null) as null_after_coalesce,
from `teamster-332318`.kipptaf_students.int_students__enrollment_daily as mem
left join
    `teamster-332318`.kipptaf_students.int_students__terms as t
    on mem.yearid = t.yearid
    and mem.schoolid = t.schoolid
    and mem.calendardate between t.term_start_date and t.term_end_date
    and mem._dbt_source_project = t._dbt_source_project
    and t.term is not null
where mem.week_start_monday is not null
```

Expected: `null_from_terms` is 1,864,931 and `null_after_coalesce` is 0. A
nonzero `null_after_coalesce` means some membership row has a null `yearid` and
the `not_null` test from Step 4 would fail CI — report it rather than deleting
the test.

- [ ] **Step 6: Compile the model**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage/src/dbt/kipptaf
```

Then, in a separate Bash call:

```bash
uv run dbt compile --select int_students__attendance_daily --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage/src/dbt/kipptaf --target prod 2>&1 | tail -n 20
```

Expected: compiles with no errors.

- [ ] **Step 7: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/students/intermediate/int_students__attendance_daily.sql src/dbt/kipptaf/models/students/intermediate/properties/int_students__attendance_daily.yml </dev/null 2>&1 | tail -n 30
```

Expected: `✔ No issues`.

- [ ] **Step 8: Commit**

Subject: `fix(dbt): left join the term spine in attendance daily`. Same
scratchpad-file mechanics and trailer as Task 1.

---

### Task 3: two `int_students__terms` defects and the stale description

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__terms.sql:61-73`
  (add a column), a new CTE before `:83`, and `:88` plus `:121-135` (the join
  and its coalesces)
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__terms.yml`

**Interfaces:**

- Consumes: `stg_powerschool__terms` (kipptaf union wrapper — the only relation
  carrying `rn`) and `int_powerschool__terms` (kipptaf union wrapper, which Task
  1's change flows into and which carries `_dbt_source_relation` from
  `union_relations`).
- Produces: `int_students__terms` with an unchanged 34-column output list and
  `_dbt_source_relation` non-null on every row.

- [ ] **Step 1: Confirm both defects are inert today**

```sql
select
    countif(rn > 1) as rn_gt_1_rows,
    count(*) as total_rows,
from `teamster-332318`.kipptaf_powerschool.stg_powerschool__terms
```

Expected: `rn_gt_1_rows` is 0. That is what makes the `rn = 1` fix a pure no-op
on today's data, so the row count of `int_students__terms` must not move.

```sql
select countif(_dbt_source_relation is null) as null_source_relation,
from `teamster-332318`.kipptaf_students.int_students__terms
```

Expected: 0 today, because no quarter currently arrives without a matching raw
`terms` row for the same `(schoolid, yearid, abbreviation)`. Task 1 does not
change that either — it adds quarters DERIVED from raw `terms` rows, which by
construction have a match. The `coalesce` is the guard for the pre-existing
`q`-only case documented in the model's own comment at lines 75-82.

- [ ] **Step 2: Carry `_dbt_source_relation` through the quarters CTE**

Old, lines 61-73:

```sql
    powerschool_quarters as (
        select
            schoolid,
            yearid,
            academic_year,
            term,
            term_start_date,
            term_end_date,
            semester,
            is_current_term,
            _dbt_source_project,
        from {{ ref("int_powerschool__terms") }}
    ),
```

New — add `_dbt_source_relation` as the first column:

```sql
    powerschool_quarters as (
        select
            _dbt_source_relation,
            schoolid,
            yearid,
            academic_year,
            term,
            term_start_date,
            term_end_date,
            semester,
            is_current_term,
            _dbt_source_project,
        from {{ ref("int_powerschool__terms") }}
    ),
```

- [ ] **Step 3: Move `rn = 1` out of the `FULL JOIN` `ON` clause**

`and p.rn = 1` inside a `FULL JOIN` `ON` decides which rows MATCH rather than
filtering `p`, so a `p` row with `rn = 2` survives as a `p`-only row with every
quarter column null. It cannot move to `WHERE` either — that collapses the full
join to an inner and drops the `q`-only rows the model's comment exists to
preserve. It has to be a filter in a CTE the join reads.

Insert this CTE immediately before the `powerschool_joined` comment block at
line 75. The columns are enumerated, not `* except (rn)`, matching the
convention the model's own comment at lines 84-86 states.

This is all 31 columns of `stg_powerschool__terms` except `rn`, in
`ordinal_position` order, read from
`kipptaf_powerschool.INFORMATION_SCHEMA.COLUMNS` on 2026-09-17. `name` is
backticked because it is BigQuery-reserved.

```sql
    powerschool_canonical as (
        select
            _dbt_source_relation,
            dcid,
            `name`,
            firstday,
            lastday,
            abbreviation,
            importmap,
            terminfo_guid,
            psguid,
            ip_address,
            whomodifiedtype,
            transaction_date,
            id,
            yearid,
            noofdays,
            schoolid,
            yearlycredithrs,
            termsinyear,
            portion,
            autobuildbin,
            isyearrec,
            periods_per_day,
            days_per_cycle,
            attendance_calculation_code,
            sterms,
            suppresspublicview,
            whomodifiedid,
            academic_year,
            fiscal_year,
            semester,
            _dbt_source_project,
        from {{ ref("stg_powerschool__terms") }}
        where rn = 1
    ),
```

Count the columns you wrote before moving on. Dropping one silently narrows
`int_students__terms`, whose final `SELECT` enumerates 34 columns drawn from
this CTE and `powerschool_quarters`.

Then change the join source and drop the predicate. Old, lines 127-135:

```sql
        from {{ ref("stg_powerschool__terms") }} as p
        full join
            powerschool_quarters as q
            on p.schoolid = q.schoolid
            and p.yearid = q.yearid
            and p.abbreviation = q.term
            and p._dbt_source_project = q._dbt_source_project
            and p.rn = 1
    )
```

New:

```sql
        from powerschool_canonical as p
        full join
            powerschool_quarters as q
            on p.schoolid = q.schoolid
            and p.yearid = q.yearid
            and p.abbreviation = q.term
            and p._dbt_source_project = q._dbt_source_project
    )
```

- [ ] **Step 4: Coalesce `_dbt_source_relation` across the full join**

A `q`-only row emits null for every `p` column including `_dbt_source_relation`,
and downstream models `regexp_extract` a region out of it. Delete the bare
projection at line 88:

```sql
            p._dbt_source_relation,
```

and add a fourth coalesce at the end of the coalesce block, after
`academic_year` at line 126:

```sql
            coalesce(
                p._dbt_source_relation, q._dbt_source_relation
            ) as _dbt_source_relation,
```

Both sides encode the region — `<district>_powerschool.stg_powerschool__terms`
and `<district>_powerschool.int_powerschool__terms` — so the downstream
`regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` resolves either way.

The final `SELECT`'s 34-column list at lines 137-173 keeps
`_dbt_source_relation` first and does not change; only where the column is
DERIVED moves.

- [ ] **Step 5: Verify the row set does not move**

```sql
with
    powerschool_canonical as (
        select *,
        from `teamster-332318`.kipptaf_powerschool.stg_powerschool__terms
        where rn = 1
    ),

    joined as (
        select
            coalesce(p._dbt_source_relation, q._dbt_source_relation) as src_rel,
            coalesce(p.schoolid, q.schoolid) as schoolid,
            coalesce(p.yearid, q.yearid) as yearid,
            coalesce(
                p._dbt_source_project, q._dbt_source_project
            ) as src_project,
            p.abbreviation,
            q.term,
        from powerschool_canonical as p
        full join
            `teamster-332318`.kipptaf_powerschool.int_powerschool__terms as q
            on p.schoolid = q.schoolid
            and p.yearid = q.yearid
            and p.abbreviation = q.term
            and p._dbt_source_project = q._dbt_source_project
    )

select
    count(*) as joined_rows,
    countif(src_rel is null) as null_source_relation,
    countif(term is not null) as quarter_rows,
    count(
        distinct if(
            term is not null,
            format('%T|%T|%T|%T', src_project, schoolid, yearid, term),
            null
        )
    ) as distinct_quarter_keys,
from joined
```

Expected: `null_source_relation` is 0, and `quarter_rows` equals
`distinct_quarter_keys`. That second equality is the model's
`[schoolid, yearid, term, _dbt_source_project]` uniqueness test scoped
`where: term is not null`, evaluated ahead of CI. The `if(..., null)` restricts
the distinct count to quarter rows so the year and semester rows, which carry a
null `term`, cannot contribute a key.

Compare `joined_rows` against the current PowerSchool-branch row count of
`int_students__terms`:

```sql
select count(*) as powerschool_branch_rows,
from `teamster-332318`.kipptaf_students.int_students__terms
where _dbt_source_project != 'kippmiami'
```

`joined_rows` must match. A larger `joined_rows` means Task 1 introduced
quarters that fan out against the raw `terms` rows; a smaller one means the
`rn = 1` filter dropped rows and the Step 1 assumption was stale.

- [ ] **Step 6: Correct the descriptions that document termbins-only sourcing**

Four places in
`src/dbt/kipptaf/models/students/intermediate/properties/int_students__terms.yml`
state that PowerSchool quarter dates come from termbins rather than the raw
terms row. After Task 1 that holds only where termbins has rows.

In the model `description`, replace:

```text
      and for Focus they are derived on Focus's quarter-type marking periods.
```

The sentence before it reads
`the per-district int_powerschool__terms source, which resolves quarter dates through termbins rather than the raw terms table's own quarter row,`
— change that clause to
`the per-district int_powerschool__terms source, which resolves quarter dates through termbins where termbins carries the quarter and through the raw terms table's own quarter record where it does not,`.

In the `data_tests:` comment, replace `which termbins supplies` with
`which int_powerschool__terms supplies`.

On the `term` column, replace `(resolved through termbins)` with
`(resolved through termbins, or through the raw terms record where termbins has no row)`.

On `term_start_date` and `term_end_date`, replace
`sourced from termbins for PowerSchool` with
`sourced from termbins for PowerSchool, or from the raw terms record's firstday and lastday where termbins has no row`.

- [ ] **Step 7: Compile and lint**

```bash
uv run dbt compile --select int_students__terms --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage/src/dbt/kipptaf --target prod 2>&1 | tail -n 20
```

Then:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/students/intermediate/int_students__terms.sql src/dbt/kipptaf/models/students/intermediate/properties/int_students__terms.yml </dev/null 2>&1 | tail -n 30
```

Expected: compiles clean, `✔ No issues`.

- [ ] **Step 8: Check the other eight `int_students__terms` consumers**

Task 1 gives historical school-years quarter rows they have never seen. Read
each and confirm its join to `int_students__terms` is either at quarter grain on
`(schoolid, yearid, term, _dbt_source_project)` or already filters
`term is not null`, and that none joins on a key the new rows could duplicate:

- `src/dbt/kipptaf/models/students/intermediate/int_students__enrollment_daily.sql`
- `src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_subjects.sql`
- `src/dbt/kipptaf/models/students/intermediate/int_extracts__course_enrollments_by_term.sql`
- `src/dbt/kipptaf/models/students/intermediate/int_extracts__course_schedule_by_term.sql`
- `src/dbt/kipptaf/models/extracts/illuminate/rpt_illuminate__terms.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_course_grades.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_gpa.sql`
- `src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_teacher_scaffold.sql`

Report any consumer whose grain the new rows would break. Do not change one
without saying so — a fan-out found here is a finding for the PR body, not a
silent edit.

- [ ] **Step 9: Commit**

Subject: `fix(dbt): filter rn and coalesce source relation in students terms`.
Same scratchpad-file mechanics and trailer as Task 1.

---

### Task 4: push and open the pull request

**Files:** none — `.github/pull_request_template.md` supplies the body.

- [ ] **Step 1: Confirm the branch is clean and ahead**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage status --short && git -C /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage log --oneline origin/main..HEAD
```

Expected: empty working tree, four commits (the spec plus Tasks 1 through 3).

- [ ] **Step 2: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-terms-quarter-coverage push 2>&1 | tail -n 10
```

- [ ] **Step 3: Open the PR**

Read `.github/pull_request_template.md` and keep every line it supplies,
answering its prompts in place. Create with `mcp__github__create_pull_request`,
base `main`. Put `Closes #5390` in the body so the PR lands on the project board
— never `gh project item-add` a PR. Carry these facts into the body: the
1,864,931 recovered days, the 1,312,174 that gain a real quarter and the 552,757
that do not, the unchanged 16,035,288 membership total as the no-fan-out proof,
and the `int_powerschool__student_course_grades_spine` blast radius of 106,976
added `kippnewark` rows against 4,232,063. End the body with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

- [ ] **Step 4: Verify the created PR**

Re-read the PR with `mcp__github__pull_request_read` and confirm the title and
body match intent. A malformed parameter succeeds with the wrong payload.

- [ ] **Step 5: Watch CI**

Poll with `gh pr checks <n> --json name,bucket,state`. Arm the Monitor in the
same turn you say you will watch it. For `claude-review` findings, invoke
`superpowers:receiving-code-review` first and post a per-finding verdict as a PR
comment. For anything else about CI, invoke `pr-ci-review`.

Expect dbt Cloud CI to build `state:modified+`, which here reaches
`int_powerschool__terms`, `int_powerschool__student_course_grades_spine`,
`int_students__terms`, `int_students__attendance_daily`, and their descendants.
Latent `severity: error` failures in models CI has never built before are
possible; query prod for the same count before assuming this change caused one.
