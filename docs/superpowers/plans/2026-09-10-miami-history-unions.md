# Miami History Unions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep 11 Miami PowerSchool history unions in kipptaf, drop the other 9,
delete the `exclude_frozen` macro, and record a verdict for every Miami
exclusion filter, closing #5193 and with it #5012.

**Architecture:** Three PRs in order. PR 1 adds 3 week columns to the package
attendance fact so kipptaf's `int_students__attendance_daily` no longer needs a
calendar-week join, then re-includes the package in `kippmiami` for one archive
rebuild. PR 1b removes the package again. PR 2 does all kipptaf work: 9 union
drops, 5 `schools` repoints, macro deletion, dead-filter deletion, docs.

**Tech Stack:** dbt 1.x on BigQuery via `uv run dbt`,
`dbt_utils.union_relations`, Dagster+ for the archive materialization, trunk for
lint.

Spec: `docs/superpowers/specs/2026-09-10-miami-history-unions-design.md`.

## Global Constraints

- All paths are under the worktree
  `/workspaces/teamster/.worktrees/cbini/chore/claude-miami-history-unions`.
  Every git call is `git -C <worktree>`. Every dbt call is
  `uv run dbt ... --project-dir <worktree>/src/dbt/<project>`.
- Never run bare `python`, `dbt`, or `dagster`. Always `uv run`.
- Warehouse DML (`update`, `delete`) never runs from Claude. The archive hooks
  run under Dagster's credentials during the one materialization Charlie
  launches from the Dagster UI.
- Before pushing SQL, YAML, or markdown:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- Local dbt builds follow the `dbt-local-dev` skill: `--defer --favor-state`
  against prod state, never `--empty`.
- Commit messages follow conventional commits and end with
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Keep the `int_students__course_sections` and
  `int_students__course_enrollments` cutover predicates. They are out of scope.
- The 6 internal-join readers and the 3 `base_powerschool__*` wrappers are out
  of scope. File follow-ups, do not fix.

## Spec amendment recorded here

The spec says PR 1 removes the `int_students__calendar_week` join from
`int_students__attendance_daily`. That join also serves the Focus branch, which
has no week columns. Task 6 therefore gives the Focus branch its own join to
`int_focus__calendar_week` inside `focus_conformed`, a Focus-internal join in
the Focus staging layer, and removes the post-union join. Both branches then
arrive with week columns and `int_students__calendar_week` has no attendance
reader.

---

## PR 1: package week fields and archive rebuild

Branch: `cbini/feat/claude-ps-adaadm-week-fields`, worktree
`/workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields`,
created with
`gh issue develop 5193 --name cbini/feat/claude-ps-adaadm-week-fields` then
`git worktree add /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields cbini/feat/claude-ps-adaadm-week-fields`.

### Task 1: Add week columns to the package attendance fact

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__ps_adaadm_daily_ctod.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__ps_adaadm_daily_ctod.yml`

**Interfaces:**

- Produces: columns `week_start_monday date`, `week_end_sunday date`,
  `week_number_academic_year int64` on every region's
  `int_powerschool__ps_adaadm_daily_ctod` and on the kipptaf union of the same
  name. Task 6 reads them as `mem.week_start_monday`, `mem.week_end_sunday`,
  `mem.week_number_academic_year`.

- [ ] **Step 1: Add the calendar-week join to the package model**

In
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql`,
after the `membershipvalue` expression (the last select item, ends
`* mv.ontrack as membershipvalue,`), add:

```sql
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.week_number_academic_year,
```

After the final `left join aci as aci_potential ...` block (last lines of the
file), add:

```sql
left join
    {{ ref("int_powerschool__calendar_week") }} as cw
    on mv.schoolid = cw.schoolid
    and tac.yearid = cw.yearid
    and mv.calendardate between cw.week_start_monday and cw.week_end_sunday
```

Left join on purpose: a membership day outside any calendar week keeps its row
with null week fields. The kipptaf inner join it replaces dropped such rows
silently; Task 6 counts them.

- [ ] **Step 2: Declare the columns in the package YAML**

Append to the `columns:` list in
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__ps_adaadm_daily_ctod.yml`:

```yaml
- name: week_start_monday
  data_type: date
- name: week_end_sunday
  data_type: date
- name: week_number_academic_year
  data_type: int64
```

- [ ] **Step 3: Declare the columns in the kipptaf union YAML**

In
`src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__ps_adaadm_daily_ctod.yml`,
before the `- name: _dbt_source_project` entry, add:

```yaml
- name: week_start_monday
  data_type: date
  description: Monday of the calendar week containing calendardate.
- name: week_end_sunday
  data_type: date
  description: Sunday of the calendar week containing calendardate.
- name: week_number_academic_year
  data_type: int64
  description: 1-based week index within the school's academic year.
```

- [ ] **Step 4: Compile the package through one district**

Run:

```bash
uv run dbt compile --select int_powerschool__ps_adaadm_daily_ctod --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields/src/dbt/kippnewark
```

Expected: `Done.` with no errors. Then confirm the compiled SQL names all 3
columns:

```bash
grep -c "week_start_monday\|week_end_sunday\|week_number_academic_year" /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields/src/dbt/kippnewark/target/compiled/powerschool/models/sis/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql
```

Expected: `6` (3 select items, 3 join predicates).

- [ ] **Step 5: Build in dev for Newark and check null rate**

Run:

```bash
uv run dbt build --select int_powerschool__ps_adaadm_daily_ctod --defer --favor-state --state <prod-state-dir> --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields/src/dbt/kippnewark
```

Then in BigQuery MCP, against the dev schema the build printed:

```sql
select
    count(*) as rows_total,
    countif(week_start_monday is null) as rows_no_week,
from `<dev-dataset>.int_powerschool__ps_adaadm_daily_ctod`
```

Expected: `rows_total` equals the prod count from
`select count(*) from kippnewark_powerschool.int_powerschool__ps_adaadm_daily_ctod`,
and `rows_no_week` is 0 or a handful. Record both numbers in the PR body.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/powerschool/models/sis/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__ps_adaadm_daily_ctod.yml src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__ps_adaadm_daily_ctod.yml </dev/null
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields commit -m "feat(powerschool): carry calendar week fields on int_powerschool__ps_adaadm_daily_ctod

Refs #5193

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

### Task 2: Re-include the package in kippmiami for the rebuild

**Files:**

- Modify: `src/dbt/kippmiami/packages.yml`
- Modify: `src/dbt/kippmiami/dbt_project.yml`

**Interfaces:**

- Consumes: nothing from Task 1 beyond being on the same branch.
- Produces: a `kippmiami` project that builds the `powerschool` package with the
  16 archive hooks, exactly as commit `ed848b22e9` did.

- [ ] **Step 1: Restore the package and hooks from the last rebuild commit**

The last re-include is commit `ed848b22e9`. Its removal is `84ceb3a6d0`. Revert
the removal onto this branch:

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields revert --no-commit 84ceb3a6d0
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields diff --cached --stat
```

Expected: exactly `src/dbt/kippmiami/dbt_project.yml` and
`src/dbt/kippmiami/packages.yml` changed. If the revert conflicts, resolve to
the content of `ed848b22e9` for those two files:

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields show ed848b22e9:src/dbt/kippmiami/dbt_project.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields show ed848b22e9:src/dbt/kippmiami/packages.yml
```

- [ ] **Step 2: Verify the hook block is intact**

```bash
grep -c "post-hook" /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields/src/dbt/kippmiami/dbt_project.yml
grep -n "local: ../powerschool" /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields/src/dbt/kippmiami/packages.yml
```

Expected: `16` and one match.

- [ ] **Step 3: Parse the kippmiami project**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields/src/dbt/kippmiami
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields/src/dbt/kippmiami
uv run dbt ls --select int_powerschool__ps_adaadm_daily_ctod --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields/src/dbt/kippmiami
```

Expected: parse succeeds; `ls` prints
`powerschool.sis.intermediate.int_powerschool__ps_adaadm_daily_ctod`.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields commit -m "chore(kippmiami): re-include the powerschool package with the 16 archive hooks for the third rebuild

Refs #5193

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

### Task 3: Open PR 1 and hand off the materialization

**Files:** none new.

- [ ] **Step 1: Push and open the PR**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-ps-adaadm-week-fields push -u origin cbini/feat/claude-ps-adaadm-week-fields
```

Open with `mcp__github__create_pull_request`, body from
`.github/pull_request_template.md`. Title:
`feat(powerschool): carry calendar week fields on the attendance fact and rebuild the Miami archive (PR 1)`.
Body states the Newark dev counts from Task 1 Step 5, `Refs #5193`, and the
Dagster step below. End with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

- [ ] **Step 2: Follow `pr-ci-review` until green, then hand off**

After merge, Charlie materializes from the Dagster UI: code location
`kippmiami`, asset group `powerschool` under `kippmiami_dbt_assets`, about 120
models, as in #5231. Nothing else triggers it.

- [ ] **Step 3: Verify the archive after materialization**

In BigQuery MCP:

```sql
select
    count(*) as rows_total,
    countif(week_start_monday is null) as rows_no_week,
    max(calendardate) as max_date,
from `teamster-332318.kippmiami_powerschool.int_powerschool__ps_adaadm_daily_ctod`
```

Expected: `rows_total` equals the pre-build count taken before merge (record it
in the PR body first), `max_date` is on or before 2026-06-30, `rows_no_week` is
0 or a handful. Post the result as a PR comment.

## PR 1b: remove the package again

### Task 4: Drop the package from kippmiami

**Files:**

- Modify: `src/dbt/kippmiami/packages.yml`
- Modify: `src/dbt/kippmiami/dbt_project.yml`

- [ ] **Step 1: New branch from origin/main**

```bash
gh issue develop 5193 --name cbini/chore/claude-kippmiami-drop-powerschool-3
git -C /workspaces/teamster fetch origin cbini/chore/claude-kippmiami-drop-powerschool-3
git worktree add /workspaces/teamster/.worktrees/cbini/chore/claude-kippmiami-drop-powerschool-3 cbini/chore/claude-kippmiami-drop-powerschool-3
```

- [ ] **Step 2: Re-apply the removal commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/chore/claude-kippmiami-drop-powerschool-3 cherry-pick 84ceb3a6d0
git -C /workspaces/teamster/.worktrees/cbini/chore/claude-kippmiami-drop-powerschool-3 show --stat HEAD
```

Expected: the two kippmiami files change and
`grep -c post-hook src/dbt/kippmiami/dbt_project.yml` prints `0`.

- [ ] **Step 3: Parse, push, open PR 1b**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-kippmiami-drop-powerschool-3/src/dbt/kippmiami
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/chore/claude-kippmiami-drop-powerschool-3/src/dbt/kippmiami
git -C /workspaces/teamster/.worktrees/cbini/chore/claude-kippmiami-drop-powerschool-3 push -u origin cbini/chore/claude-kippmiami-drop-powerschool-3
```

Title:
`chore(kippmiami): remove the powerschool package again after the third archive rebuild (PR 1b)`.
Body: `Refs #5193`, one line saying the tables stay.

## PR 2: kipptaf

Branch: the existing worktree
`/workspaces/teamster/.worktrees/cbini/chore/claude-miami-history-unions`
(already holds the spec and this plan). Before starting, merge `origin/main` so
PR 1's kipptaf YAML is present: invoke `resuming-a-branch`, then
`git -C /workspaces/teamster/.worktrees/cbini/chore/claude-miami-history-unions merge origin/main`.

All paths below are relative to `<wt>/src/dbt/kipptaf/` where `<wt>` is that
worktree.

### Task 5: Drop the 9 Miami relations and trim the source file

**Files:**

- Modify: `models/powerschool/staging/stg_powerschool__schools.sql:8`
- Modify: `models/powerschool/staging/stg_powerschool__assignmentscore.sql:8`
- Modify: `models/powerschool/staging/stg_powerschool__sectionteacher.sql:8`
- Modify: `models/powerschool/staging/stg_powerschool__roledef.sql:8`
- Modify: `models/powerschool/staging/stg_powerschool__calendar_day.sql:8`
- Modify: `models/powerschool/intermediate/int_powerschool__teachers.sql:8`
- Modify: `models/powerschool/intermediate/int_powerschool__calendar_day.sql:8`
- Modify:
  `models/powerschool/intermediate/int_powerschool__calendar_week.sql:12`
- Modify:
  `models/powerschool/intermediate/int_powerschool__calendar_rollup.sql:12-14`
- Modify: `models/powerschool/sources-kippmiami.yml`

**Interfaces:**

- Produces: 9 unions with no `kippmiami` rows. Tasks 7 and 9 delete filters that
  depended on those rows.

- [ ] **Step 1: Delete the 9 source lines**

In each of the 9 SQL files, delete the one line (or, for `calendar_rollup`, the
3-line `source(` block) that names `"kippmiami_powerschool"`. Verify:

```bash
cd <wt>/src/dbt/kipptaf/models && grep -l '"kippmiami_powerschool"' powerschool/staging/stg_powerschool__{schools,assignmentscore,sectionteacher,roledef,calendar_day}.sql powerschool/intermediate/int_powerschool__{teachers,calendar_day,calendar_week,calendar_rollup}.sql
```

Expected: no output.

- [ ] **Step 2: Confirm exactly 11 unions still name the archive**

```bash
cd <wt>/src/dbt/kipptaf/models && grep -rl '"kippmiami_powerschool"' --include='*.sql' . | sort
```

Expected, exactly these 11:

```text
./powerschool/base/base_powerschool__final_grades.sql
./powerschool/intermediate/int_powerschool__ada.sql
./powerschool/intermediate/int_powerschool__attendance_streak.sql
./powerschool/intermediate/int_powerschool__course_enrollments_union.sql
./powerschool/intermediate/int_powerschool__final_grades_rollup.sql
./powerschool/intermediate/int_powerschool__gpa_cumulative.sql
./powerschool/intermediate/int_powerschool__gpa_term.sql
./powerschool/intermediate/int_powerschool__ps_adaadm_daily_ctod.sql
./powerschool/intermediate/int_powerschool__sections_union.sql
./powerschool/staging/stg_powerschool__courses.sql
./powerschool/staging/stg_powerschool__storedgrades.sql
```

- [ ] **Step 3: Trim `sources-kippmiami.yml` to the 11 kept tables**

The source tables the 11 unions read are: `stg_powerschool__storedgrades`,
`stg_powerschool__courses`, `base_powerschool__final_grades`,
`base_powerschool__sections`, `base_powerschool__course_enrollments`,
`int_powerschool__final_grades_rollup`, `int_powerschool__gpa_term`,
`int_powerschool__gpa_cumulative`, `int_powerschool__ps_adaadm_daily_ctod`,
`int_powerschool__ada`, `int_powerschool__attendance_streak`. Delete every other
`- name:` entry (each is a 9-line block). Replace the `description:` with:

```yaml
description: >-
  Miami's PowerSchool archive (final ODBC pull 2026-07-01; Miami's SIS moved to
  Focus). Permanent history source for stored grades, attendance, and the course
  enrollments they hang off (#5193). Rebuilt from the frozen externals with the
  8400 Focus prefix on student_number and an AY2025 bound applied (#5012). The
  dataset must not be dropped. Declared BQ-native (plain schema, no target
  branch) so every target reads the prod tables directly.
```

Verify:

```bash
grep -c "      - name: " <wt>/src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml
```

Expected: `11`.

- [ ] **Step 4: Parse**

```bash
uv run dbt parse --project-dir <wt>/src/dbt/kipptaf
```

Expected: success. A `Source ... not found` error names a union whose source
entry was deleted by mistake; restore that entry.

- [ ] **Step 5: Commit**

```bash
git -C <wt> add -u
git -C <wt> commit -m "refactor(kipptaf): drop Miami from 9 PowerSchool unions, keep the 11 history sources

Refs #5193

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

### Task 6: Attendance daily reads week fields from both branches

**Files:**

- Modify: `models/students/intermediate/int_students__attendance_daily.sql`

**Interfaces:**

- Consumes: `week_start_monday`, `week_end_sunday`, `week_number_academic_year`
  on the kipptaf `int_powerschool__ps_adaadm_daily_ctod` union (Task 1) and on
  `int_focus__calendar_week`.
- Produces: the same 3 output columns as today, now sourced from `mem`.

- [ ] **Step 1: Add the week join to the Focus branch**

In `focus_conformed`, after
`if(ad.daily_code = 'U', 'A', ad.daily_code) as att_code,` add:

```sql
            fcw.week_start_monday,
            fcw.week_end_sunday,
            fcw.week_number_academic_year,
```

After the line
`inner join focus_schools as fs on ad.schoolid = fs.focus_school_id` add:

```sql
        left join
            {{ ref("int_focus__calendar_week") }} as fcw
            on ad.schoolid = fcw.schoolid
            and ad.academic_year = fcw.academic_year
            and ad.school_date between fcw.week_start_monday and fcw.week_end_sunday
            and ad._dbt_source_project = fcw._dbt_source_project
```

`ad.schoolid` and `fcw.schoolid` are both the Focus internal school id, so no
`focus_schools` translation is needed on this join.

- [ ] **Step 2: Switch the 3 output columns and remove the post-union join**

At lines 170 to 172 change:

```sql
            cw.week_start_monday,
            cw.week_end_sunday,
            cw.week_number_academic_year,
```

to:

```sql
            mem.week_start_monday,
            mem.week_end_sunday,
            mem.week_number_academic_year,
```

Delete the block at lines 238 to 243:

```sql
        inner join
            {{ ref("int_students__calendar_week") }} as cw
            on mem.yearid = cw.yearid
            and mem.schoolid = cw.schoolid
            and mem.calendardate between cw.week_start_monday and cw.week_end_sunday
            and mem._dbt_source_project = cw._dbt_source_project
```

Verify no `cw.` remains:

```bash
grep -c "cw\." <wt>/src/dbt/kipptaf/models/students/intermediate/int_students__attendance_daily.sql
```

Expected: `0`.

- [ ] **Step 3: Build and compare to prod**

```bash
uv run dbt build --select int_students__attendance_daily --defer --favor-state --state <prod-state-dir> --project-dir <wt>/src/dbt/kipptaf
```

Then in BigQuery MCP, with `<dev>` the dev dataset the build printed:

```sql
with
    dev as (
        select _dbt_source_project, academic_year <= 2025 as is_hist, count(*) as n,
        from `<dev>.int_students__attendance_daily`
        group by 1, 2
    ),
    prod as (
        select _dbt_source_project, academic_year <= 2025 as is_hist, count(*) as n,
        from `teamster-332318.kipptaf_students.int_students__attendance_daily`
        group by 1, 2
    )
select
    coalesce(dev._dbt_source_project, prod._dbt_source_project) as project,
    coalesce(dev.is_hist, prod.is_hist) as is_hist,
    prod.n as prod_n,
    dev.n as dev_n,
    dev.n - prod.n as delta,
from dev
full join prod using (_dbt_source_project, is_hist)
order by 1, 2
```

Expected: `delta` is 0 or a small positive number on every row. A positive delta
is a day that the old inner join dropped and the left join keeps.
`kippmiami, is_hist=true` must show `prod_n = 793259` and `dev_n >= 793259`. Any
negative delta stops the task.

Also confirm null weeks are rare:

```sql
select _dbt_source_project, countif(week_start_monday is null) as no_week, count(*) as n
from `<dev>.int_students__attendance_daily`
group by 1
```

Expected: `no_week` equals the positive `delta` from the query above, per
project.

- [ ] **Step 4: Commit**

```bash
git -C <wt> add -u
git -C <wt> commit -m "refactor(students): read attendance week fields from the SIS facts, drop the calendar_week join

Refs #5193

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

### Task 7: Repoint 5 schools readers and simplify int_students__schools

**Files:**

- Modify: `models/students/intermediate/int_students__schools.sql`
- Modify:
  `models/assessments/intermediate/int_assessments__academic_goals.sql:14-18`
- Modify:
  `models/google/sheets/intermediate/int_google_sheets__topline_aggregate_goals.sql:35`
- Modify:
  `models/finance/intermediate/int_finance__enrollment_targets.sql:18-21`
- Modify:
  `models/extracts/tableau/intermediate/int_tableau__gradebook_audit_teacher_scaffold.sql:99-102`
- Modify: `models/kippadb/intermediate/int_kippadb__roster.sql:19-23`

**Interfaces:**

- Consumes: `int_students__schools` columns `school_number`, `name`,
  `abbreviation`, `school_level`, `location_key`, `_dbt_source_project`,
  `_dbt_source_relation`.

- [ ] **Step 1: Simplify `int_students__schools`**

Replace lines 19 to 26:

```sql
    powerschool_filtered as (
        select p.*,
        from {{ ref("stg_powerschool__schools") }} as p
        where p._dbt_source_project != 'kippmiami'
    )

select *,
from powerschool_filtered
```

with:

```sql
    powerschool_schools as (select *, from {{ ref("stg_powerschool__schools") }})

select *,
from powerschool_schools
```

The `stg_powerschool__schools` union no longer carries Miami after Task 5, so
the filter is a no-op. Keeping a named CTE keeps the
`full union all corresponding` shape unchanged.

- [ ] **Step 2: Repoint `int_assessments__academic_goals`**

Line 18, change `{{ ref("stg_powerschool__schools") }}` to
`{{ ref("int_students__schools") }}`. Line 16 keeps
`regexp_extract(s._dbt_source_relation, r'kipp(\w+)_')`; the Focus relation is
`...kippmiami_focus...` so `region` still resolves to `Miami`.

- [ ] **Step 3: Repoint `int_google_sheets__topline_aggregate_goals`**

Line 35, change `{{ ref("stg_powerschool__schools") }}` to
`{{ ref("int_students__schools") }}`.

- [ ] **Step 4: Repoint `int_finance__enrollment_targets`**

Line 21, change `{{ ref("stg_powerschool__schools") }}` to
`{{ ref("int_students__schools") }}`.

- [ ] **Step 5: Repoint `int_tableau__gradebook_audit_teacher_scaffold`**

Line 100, change `{{ ref("stg_powerschool__schools") }}` to
`{{ ref("int_students__schools") }}`. The join already matches on
`_dbt_source_project`.

- [ ] **Step 6: Repoint `int_kippadb__roster`**

Line 21, change `{{ ref("stg_powerschool__schools") }}` to
`{{ ref("int_students__schools") }}`. The join already matches on
`_dbt_source_project`.

- [ ] **Step 7: Build the 6 models and compare Miami and NJ counts**

```bash
uv run dbt build --select int_students__schools int_assessments__academic_goals int_google_sheets__topline_aggregate_goals int_finance__enrollment_targets int_tableau__gradebook_audit_teacher_scaffold int_kippadb__roster --defer --favor-state --state <prod-state-dir> --project-dir <wt>/src/dbt/kipptaf
```

For each of the 5 repointed models, in BigQuery MCP (substitute the model and
its prod dataset; `region`-keyed models use `region = 'Miami'`, the rest use
`_dbt_source_project = 'kippmiami'`):

```sql
select
    'prod' as src, countif(_dbt_source_project = 'kippmiami') as miami, countif(_dbt_source_project != 'kippmiami') as nj,
from `teamster-332318.<prod_dataset>.<model>`
union all
select 'dev', countif(_dbt_source_project = 'kippmiami'), countif(_dbt_source_project != 'kippmiami'),
from `<dev>.<model>`
```

Expected per model: `nj` identical between prod and dev. `miami` on dev is
greater than or equal to prod (Focus adds the 3 newest schools where the sheet
has rows) and never less. Prod baselines measured 2026-09-10:
`int_google_sheets__topline_aggregate_goals` 101 Miami rows,
`int_finance__enrollment_targets` 59, `int_assessments__academic_goals` 36.

- [ ] **Step 8: Commit**

```bash
git -C <wt> add -u
git -C <wt> commit -m "refactor(kipptaf): read Miami school attributes from int_students__schools

Refs #5193

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

### Task 8: Delete exclude_frozen and inline the 7 live Clever gates

**Files:**

- Modify: `macros/utils.sql:11-19` (delete)
- Modify: `dbt_project.yml:38-43` (delete)
- Modify: `models/extracts/clever/rpt_clever__enrollments.sql:17,32` (delete)
- Modify: `models/extracts/clever/rpt_clever__schools.sql:25` (delete)
- Modify: `models/extracts/clever/rpt_clever__staff.sql:20,40,59`
- Modify: `models/extracts/clever/rpt_clever__teachers.sql:26,49`
- Modify: `models/extracts/clever/rpt_clever__sections.sql:15,39,94,110`
- Modify: `models/extracts/clever/rpt_clever__students.sql:92`

- [ ] **Step 1: Delete the macro and var**

In `macros/utils.sql` delete lines 11 to 19 (the comment block starting
`{# Drops code locations whose PowerSchool instance is frozen` through
`{%- endmacro %}`).

In `dbt_project.yml` delete lines 38 to 43 (the 5 comment lines starting
`# Code locations whose PowerSchool instance is frozen` and
`frozen_powerschool_code_locations: [kippmiami]`).

- [ ] **Step 2: `rpt_clever__enrollments`, delete 2 dead calls**

Line 15 to 17 become:

```sql
where cc.dateleft >= current_date('{{ var("local_timezone") }}')
```

Line 32 becomes:

```sql
where enroll_status in (0, -1)
```

- [ ] **Step 3: `rpt_clever__schools`, delete 1 dead call**

Line 25 becomes:

```sql
    state_excludefromreporting = 0
```

- [ ] **Step 4: `rpt_clever__staff`, inline 2, delete 1**

Line 20: `and {{ exclude_frozen("home_work_location_dagster_code_location") }}`
becomes `and home_work_location_dagster_code_location != 'kippmiami'`.

Line 40: `{{ exclude_frozen("dagster_code_location") }}` becomes
`dagster_code_location != 'kippmiami'`.

Lines 57 to 59 (the `schools` gate) become:

```sql
        where state_excludefromreporting = 0
```

- [ ] **Step 5: `rpt_clever__teachers`, inline 2**

Line 26: `and {{ exclude_frozen("home_work_location_dagster_code_location") }}`
becomes `and home_work_location_dagster_code_location != 'kippmiami'`.

Line 49: `{{ exclude_frozen("dagster_code_location") }}` becomes
`dagster_code_location != 'kippmiami'`.

- [ ] **Step 6: `rpt_clever__sections`, inline 2, delete 1, unwrap 1**

Line 15:
`and {{ exclude_frozen("sr.home_work_location_dagster_code_location") }}`
becomes `and sr.home_work_location_dagster_code_location != 'kippmiami'`.

Lines 37 to 39 (the `schools` gate) become:

```sql
        where state_excludefromreporting = 0
```

Line 94: `from {{ ref("base_powerschool__sections") }} as sec` becomes
`from {{ ref("int_students__course_sections") }} as sec`.

Line 110: `and {{ exclude_frozen("sec._dbt_source_project") }}` becomes
`and sec._dbt_source_project != 'kippmiami'`. Add the comment line above it:

```sql
            -- Miami rosters into Clever from Focus, not from this feed
```

- [ ] **Step 7: `rpt_clever__students`, inline 1**

Line 92: `and {{ exclude_frozen("sr._dbt_source_project") }}` becomes
`and sr._dbt_source_project != 'kippmiami'`.

- [ ] **Step 8: Verify nothing references the macro or var**

```bash
cd <wt> && grep -rn "exclude_frozen\|frozen_powerschool_code_locations" src/dbt/ --include='*.sql' --include='*.yml' --include='*.md'
```

Expected: no output. Any `.md` hit under `src/dbt/` is a doc to update in the
same commit.

- [ ] **Step 9: Build the 6 Clever feeds and diff NJ against prod**

```bash
uv run dbt build --select rpt_clever__enrollments rpt_clever__schools rpt_clever__staff rpt_clever__teachers rpt_clever__sections rpt_clever__students --defer --favor-state --state <prod-state-dir> --project-dir <wt>/src/dbt/kipptaf
```

For each feed, in BigQuery MCP:

```sql
select
    (select count(*) from `teamster-332318.kipptaf_extracts.<feed>`) as prod_n,
    (select count(*) from `<dev>.<feed>`) as dev_n,
    (
        select count(*)
        from (
            select * from `teamster-332318.kipptaf_extracts.<feed>`
            except distinct
            select * from `<dev>.<feed>`
        )
    ) as prod_not_dev,
    (
        select count(*)
        from (
            select * from `<dev>.<feed>`
            except distinct
            select * from `teamster-332318.kipptaf_extracts.<feed>`
        )
    ) as dev_not_prod
```

Expected: all four differences are 0 for every feed. Clever never received Miami
rows, so the whole output must be identical.

- [ ] **Step 10: Commit**

```bash
git -C <wt> add -u
git -C <wt> commit -m "refactor(clever): delete exclude_frozen, inline the 7 live Miami gates

Refs #5193
Closes #4670

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

### Task 9: Delete the 8 dead literals and convert the CRDC regexps

**Files:**

- Modify: `models/extracts/illuminate/rpt_illuminate__roles.sql:20-23`
- Modify: `models/extracts/illuminate/rpt_illuminate__sites.sql:41-42`
- Modify:
  `models/extracts/tableau/intermediate/int_tableau__fresh_enrollment_scaffold.sql:16`
- Modify: `models/extracts/parentsquare/rpt_parentsquare__staff.sql:10`
- Modify: `models/extracts/parentsquare/rpt_parentsquare__schools.sql:33-36`
- Modify:
  `models/powerschool/intermediate/int_powerschool__gradebook_assignment_scores_rollup.sql:43`
- Modify: `models/extracts/deanslist/rpt_deanslist__missing_assignments.sql:13`
- Modify: `models/extracts/tableau/rpt_tableau__crdc_roster.sql:164,181,247`

- [ ] **Step 1: `rpt_illuminate__roles`**

Lines 19 to 23 become:

```sql
    on sch.state_excludefromreporting = 0
```

Delete the 2 comment lines about Miami leaving Illuminate along with the
predicate.

- [ ] **Step 2: `rpt_illuminate__sites`**

Lines 41 to 42 become:

```sql
where state_excludefromreporting = 0
```

- [ ] **Step 3: `int_tableau__fresh_enrollment_scaffold`**

Line 16 becomes:

```sql
        where state_excludefromreporting = 0
```

- [ ] **Step 4: `rpt_parentsquare__staff`**

Line 10 becomes:

```sql
        where state_excludefromreporting = 0
```

- [ ] **Step 5: `rpt_parentsquare__schools`**

Lines 33 to 36: delete the 3 comment lines that explain the Miami carve-out and
change the predicate to:

```sql
        where state_excludefromreporting = 0
```

- [ ] **Step 6: `int_powerschool__gradebook_assignment_scores_rollup`**

Delete line 43, `where _dbt_source_project != 'kippmiami'`. The `from` line is
followed directly by `group by`.

- [ ] **Step 7: `rpt_deanslist__missing_assignments`**

Delete line 13, `and _dbt_source_project != 'kippmiami'`.

- [ ] **Step 8: `rpt_tableau__crdc_roster`**

Line 164: `from {{ ref("base_powerschool__course_enrollments") }} as c` becomes
`from {{ ref("int_students__course_enrollments") }} as c`.

Line 181:
`and regexp_extract(c._dbt_source_relation, r'(kipp\w+)_') != 'kippmiami'`
becomes `and c._dbt_source_project != 'kippmiami'`.

Line 247:
`and regexp_extract(_dbt_source_relation, r'(kipp\w+)_') != 'kippmiami'` becomes
`and _dbt_source_project != 'kippmiami'`.

The `-- miami does their own submission` comments stay; both filters are live
because `storedgrades` keeps Miami.

- [ ] **Step 9: Confirm the literal inventory**

```bash
cd <wt>/src/dbt/kipptaf/models && grep -rn "not like '%kippmiami%'\|!= 'kippmiami'\|region != 'Miami'" --include='*.sql' . | wc -l
```

Expected: `50` (51 on `main`, minus 8 deleted, plus 7 inlined from the macro).
Also:

```bash
grep -rn "regexp_extract([a-z._]*_dbt_source_relation, r'(kipp\\\\w+)_') != 'kippmiami'" --include='*.sql' <wt>/src/dbt/kipptaf/models
```

Expected: no output.

- [ ] **Step 10: Build the 8 touched models and check Miami counts**

```bash
uv run dbt build --select rpt_illuminate__roles rpt_illuminate__sites int_tableau__fresh_enrollment_scaffold rpt_parentsquare__staff rpt_parentsquare__schools int_powerschool__gradebook_assignment_scores_rollup rpt_deanslist__missing_assignments rpt_tableau__crdc_roster --defer --favor-state --state <prod-state-dir> --project-dir <wt>/src/dbt/kipptaf
```

For each, the same prod-versus-dev row-count query as Task 8 Step 9. Expected:
identical for all 8. For `rpt_tableau__crdc_roster` additionally:

```sql
select countif(_dbt_source_project = 'kippmiami') as miami from `<dev>.rpt_tableau__crdc_roster`
```

Expected: `0`.

- [ ] **Step 11: Commit**

```bash
git -C <wt> add -u
git -C <wt> commit -m "refactor(kipptaf): delete 8 dead Miami literals, read CRDC project from _dbt_source_project

Refs #5193

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

### Task 10: Full downstream build and history checks

**Files:** none.

- [ ] **Step 1: Build everything downstream of the changed models**

```bash
uv run dbt build --select state:modified+ --defer --favor-state --state <prod-state-dir> --project-dir <wt>/src/dbt/kipptaf
```

Expected: no errors. A compile error naming a column that came only from a
dropped Miami relation is a reader that needs a verdict; add it to the PR body
and fix in place.

- [ ] **Step 2: Course-enrollment history intact**

```sql
select
    count(*) as sections,
    countif(c.course_key is null) as no_course,
from `<dev>.dim_course_sections` as s
left join `<dev>.dim_courses` as c using (course_key)
where s._dbt_source_project = 'kippmiami' and s.terms_academic_year <= 2025
```

Expected: `sections = 3433`, `no_course = 0`.

- [ ] **Step 3: Dropped unions carry no Miami rows**

For each of the 9 dropped unions, in its dev dataset:

```sql
select count(*) from `<dev>.<union>` where _dbt_source_project = 'kippmiami'
```

Expected: `0` for all 9.

- [ ] **Step 4: Kept unions match prod**

For each of the 11 kept unions:

```sql
select
    (select count(*) from `teamster-332318.<prod_dataset>.<union>` where _dbt_source_project = 'kippmiami') as prod_miami,
    (select count(*) from `<dev>.<union>` where _dbt_source_project = 'kippmiami') as dev_miami
```

Expected: equal for all 11.

- [ ] **Step 5: `dim_school_calendars` Miami history is gone as accepted**

```sql
select countif(academic_year <= 2025) as hist, countif(academic_year >= 2026) as cur
from `<dev>.dim_school_calendars` where _dbt_source_project = 'kippmiami'
```

Expected: `hist = 0`, `cur > 0`. Record both in the PR body as the accepted
loss.

### Task 11: Docs, lint, PR

**Files:**

- Modify:
  `docs/superpowers/specs/2026-09-08-miami-powerschool-retirement-design.md`
  (append a revision note)
- Modify: `src/dbt/kipptaf/CLAUDE.md` if it mentions `exclude_frozen` (check
  with grep; on `main` it does not)

- [ ] **Step 1: Revision note on the 2026-09-08 spec**

Append after the last line of
`docs/superpowers/specs/2026-09-08-miami-powerschool-retirement-design.md`:

```markdown
## Revision 2026-09-10 (#5193)

Steps 4 and 5 are superseded by `2026-09-10-miami-history-unions-design.md`. 11
unions keep the `kippmiami` relation permanently: stored grades, attendance, and
course enrollments. The other 9 dropped it. `exclude_frozen` and its var were
deleted; the 7 live call sites are inline literals.
```

- [ ] **Step 2: Lint every changed file**

```bash
cd <wt> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git -C <wt> diff --name-only origin/main) </dev/null
```

Expected: `No issues`. Fix anything reported; markdownlint MD rules fire only
here and in CI.

- [ ] **Step 3: Commit, push, open PR 2**

```bash
git -C <wt> add -u
git -C <wt> commit -m "docs: record the Miami history union decision on the retirement spec

Refs #5193

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git -C <wt> push -u origin cbini/chore/claude-miami-history-unions
```

Title:
`refactor(kipptaf): keep 11 Miami history unions, drop 9, delete exclude_frozen (PR 2)`.
Body from `.github/pull_request_template.md`, with the Task 6, 7, 8, 9, 10
counts, `Closes #5193`, `Refs #5012`, `Closes #4670`. End with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

- [ ] **Step 4: Follow `pr-ci-review` to green and squash merge**

### Task 12: Record verdicts and close out #5012

**Files:** none in the repo.

- [ ] **Step 1: Post the verdict comment on #5193**

After PR 2 merges, post with `mcp__github__add_issue_comment`, one line per
paragraph, no hard wraps. Content: the three tables from the spec ("Keep, 11",
"Drop, 9", "Filters that stay, 50") plus the deleted list (8 literals, 5 calls,
7 inlined), each with file and final line number taken from `main` after merge
via the inventory greps:

```bash
cd /workspaces/teamster/src/dbt/kipptaf/models && grep -rn "not like '%kippmiami%'\|!= 'kippmiami'\|region != 'Miami'" --include='*.sql' . | sort
```

- [ ] **Step 2: Comment on #5012**

State that steps 4 and 5 are done under the revised scope, name the 11 permanent
unions, and link the spec. Then close #5012 with `state_reason: completed` via
`mcp__github__issue_write` once #5193 is closed by PR 2.

- [ ] **Step 3: File the follow-up issue**

`mcp__github__issue_write`, structured on
`.github/ISSUE_TEMPLATE/feature_request.md`, title
`refactor(dbt): move 6 PowerSchool-internal joins from kipptaf into the powerschool package`.
Body lists `rpt_tableau__student_course_grades`,
`rpt_deanslist__transcript_grades`, `bridge_course_section_teachers`,
`rpt_clever__sections`, `int_powerschool__gradebook_assignments_scores`,
`rpt_tableau__gradebook_assignments`, with the join each rebuilds. Labels:
`refactor`, `dbt`, `powerschool`. `Refs #5012`.

- [ ] **Step 4: Widen #3999**

Comment on #3999 that `base_powerschool__sections` (9 readers) and
`base_powerschool__course_enrollments` (39 readers) are the same passthrough
pattern and belong in its scope.
