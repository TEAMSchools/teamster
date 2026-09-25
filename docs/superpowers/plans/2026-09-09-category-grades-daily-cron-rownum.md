# Category grades daily cron and row_number dedupe implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut `int_powerschool__category_grades` from about 205 slot hours a
week in Newark to under 1 by building it once a day and replacing its
`array_agg` dedupe with a `row_number` pick.

**Architecture:** Two package-level changes in `src/dbt/powerschool`. A
`meta.dagster.automation_condition.cron_schedule` on the model and its pivot
swaps the eager table condition for a midnight tick (the translator in
`src/teamster/libraries/dbt/dagster_dbt_translator.py` reads it). The model SQL
replaces `dbt_utils.deduplicate` with a `row_number` window in a named column
and a `where rn = 1` filter in the next CTE. Output columns and tests are
unchanged.

**Tech Stack:** dbt on BigQuery, `uv run dbt`, BigQuery MCP for parity checks,
trunk for lint.

Spec:
`docs/superpowers/specs/2026-09-09-category-grades-daily-cron-rownum-design.md`.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum`.
  Every path below is relative to it. Every git call is `git -C <worktree>`.
- Cron tick is `0 0 * * *`, no `cron_timezone`.
- Dedupe partition is `studentid, yearid, course_number, storecode`; order is
  `is_dropped_section asc, percent_grade desc`. Do not change either.
- No inline SQL comments for rationale. Rationale goes in the properties
  `description`.
- Package models have no vars standalone: build through `src/dbt/kippnewark`
  with
  `--target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod`.
  The dev build lands in `zz_cbini_kippnewark_powerschool`.
- dbt Cloud CI builds kipptaf only. The package model is verified by the local
  build in Task 1, not by CI.
- Commit messages end with
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: row_number dedupe and cron on `int_powerschool__category_grades`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__category_grades.sql:1-63`
- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__category_grades.yml:1-2`

**Interfaces:**

- Consumes: `enr_gr` CTE as it exists today (lines 3 to 53).
- Produces: the same 18 output columns; a properties `config` block that Task 2
  mirrors on the pivot.

- [ ] **Step 1: Baseline the prod table**

Run in the BigQuery MCP and save the row:

```sql
select
    count(*) as n,
    count(distinct format('%T|%T|%T|%T', studentid, yearid, course_number, storecode)) as grain,
    round(sum(percent_grade), 2) as sum_pct,
    round(sum(percent_grade_y1_running), 2) as sum_y1,
    countif(is_dropped_section) as n_dropped,
    countif(is_current) as n_current,
    sum(sectionid) as sum_sec,
    count(citizenship_grade) as n_ctz,
from `teamster-332318`.kippnewark_powerschool.int_powerschool__category_grades
```

Expected on 2026-09-09: `n` 6078717, `grain` 6078717. Prod rebuilds during the
day, so re-run this right before Step 6 if more than an hour passes.

- [ ] **Step 2: Replace the dedupe CTE**

In `int_powerschool__category_grades.sql`, delete lines 2 and 55 to 63 (the
`trunk-ignore(sqlfluff/ST03)` line and the `deduplicate` CTE) and put this in
place of the `deduplicate` CTE:

```sql
    ranked as (
        select
            *,

            row_number() over (
                partition by studentid, yearid, course_number, storecode
                order by is_dropped_section asc, percent_grade desc
            ) as rn,
        from enr_gr
    ),

    deduplicate as (select * except (rn) from ranked where rn = 1)
```

The file then reads
`with enr_gr as (...), ranked as (...), deduplicate as (...)` followed by the
unchanged final `select ... from deduplicate`.

- [ ] **Step 3: Add the cron and description to the properties yml**

Replace the first two lines of `properties/int_powerschool__category_grades.yml`
(`models:` and `  - name: int_powerschool__category_grades`) with:

```yaml
models:
  - name: int_powerschool__category_grades
    description: |
      One row per student, year, course, and termbin storecode, with the
      category grade from storedgrades or pgfinalgrades and the best section
      picked per row.

      Built once a day at local midnight instead of eagerly. Every consumer is
      a daily batch: the DeansList final-grades extract at 01:25, and the
      Tableau gradebook batch plus kipptaf `int_students__category_grades` at
      04:00. Eager rebuilds ran 68 times a day in Newark at 26 slot-minutes
      each, 205 slot hours a week, for freshness nothing read. Refs #5213.

      The section pick is a `row_number` window, not
      `dbt_utils.deduplicate`. The macro compiles to one
      `array_agg(... limit 1)` per column, 16 here, and BigQuery runs a
      partial aggregate for each inside the join stage. Measured on Newark
      prod tables with identical output: 12.1 slot-minutes for the macro,
      3.2 for the window.
    config:
      meta:
        dagster:
          automation_condition:
            cron_schedule: 0 0 * * *
```

Leave the `columns:` list below it untouched.

- [ ] **Step 4: Install packages in the worktree**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum/src/dbt/kippnewark
```

Expected: ends with `Installed from <local>` lines and no error.

- [ ] **Step 5: Build the model into the dev schema**

```bash
uv run dbt build --select int_powerschool__category_grades \
  --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum/src/dbt/kippnewark \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippnewark/target/prod
```

Expected:
`1 of 2 OK created sql table model zz_cbini_kippnewark_powerschool.int_powerschool__category_grades`
and `2 of 2 PASS unique_combination_of_columns...`. If it fails with
`Could not find manifest`, the `--state` path is wrong; it must be the absolute
main-checkout path above.

- [ ] **Step 6: Compare dev to prod**

Run the Step 1 query again with the table changed to
`` `teamster-332318`.zz_cbini_kippnewark_powerschool.int_powerschool__category_grades ``.

Pass criteria, against a fresh prod baseline:

- `n`, `grain`, `sum_pct`, `sum_y1`, `n_dropped`, `n_current` equal.
- `sum_sec` and `n_ctz` may differ. If `n_ctz` differs by more than 6000 rows
  (0.1% of `n`), the pick changed: stop and re-read Step 2.

If prod rebuilt between the two queries, the grade sums can drift by a few
hundred. Re-run both in the same minute before judging.

- [ ] **Step 7: Confirm the compiled plan has no `SHARD_ARRAY_AGG`**

Run in the BigQuery MCP:

```sql
select s.name, s.records_read, s.records_written, round(s.slot_ms / 60000, 1) as slot_min
from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT, unnest(job_stages) as s
where creation_time >= timestamp_sub(current_timestamp(), interval 1 hour)
  and query like '%zz_cbini_kippnewark_powerschool%int_powerschool__category_grades%'
  and statement_type = 'CREATE_TABLE_AS_SELECT'
  and exists (select 1 from unnest(s.steps) as st, unnest(st.substeps) as sub where sub like '%ARRAY_AGG%')
```

Expected: 0 rows.

- [ ] **Step 8: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/powerschool/models/sis/intermediate/int_powerschool__category_grades.sql \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__category_grades.yml </dev/null
```

Expected: `No issues`. A `fmt` finding means run
`/workspaces/teamster/.trunk/tools/trunk fmt <file>` on that file and re-check.

- [ ] **Step 9: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum add -u
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

with `commit-msg.txt`:

```text
perf(powerschool): build int_powerschool__category_grades once a day and pick sections with row_number

Refs #5213

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 2: cron on `int_powerschool__category_grades_pivot`

**Files:**

- Modify:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__category_grades_pivot.yml:1-4`

**Interfaces:**

- Consumes: the `config:` block shape from Task 1 Step 3.
- Produces: nothing downstream in this plan.

- [ ] **Step 1: Add the cron and description**

Replace the first four lines of the file (`models:`, `  - name: ...`,
`    config:`, `      materialized: table`) with:

```yaml
models:
  - name: int_powerschool__category_grades_pivot
    description: |
      Category grades pivoted to one row per student, year, school, reporting
      term, and course, with running year-to-date columns.

      Built once a day at local midnight on the same tick as its parent
      `int_powerschool__category_grades`, so `~any_deps_in_progress` builds it
      after the parent. Its only consumer, `rpt_deanslist__final_grades`, is
      extracted at 01:25. Refs #5213.
    config:
      materialized: table
      meta:
        dagster:
          automation_condition:
            cron_schedule: 0 0 * * *
```

Leave `data_tests:` and `columns:` untouched.

- [ ] **Step 2: Parse the project**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum/src/dbt/kippnewark --target dev
```

Expected: `Performance info` line and no `Compilation Error`. Then confirm the
meta landed:

```bash
grep -c '"cron_schedule": "0 0 \* \* \*"' /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum/src/dbt/kippnewark/target/manifest.json
```

Expected: `1` (`manifest.json` is a single line, so the count is 1 when the meta
landed and 0 when it did not).

- [ ] **Step 3: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__category_grades_pivot.yml </dev/null
```

Expected: `No issues`.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum add -u
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum commit -F /workspaces/teamster/.claude/scratch/commit-msg.txt
```

with `commit-msg.txt`:

```text
perf(powerschool): build int_powerschool__category_grades_pivot on the same midnight tick as its parent

Refs #5213

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 3: push, pull request, corrected diagnosis on the issue

**Files:**

- Read: `.github/pull_request_template.md`

- [ ] **Step 1: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-category-grades-daily-cron-rownum push -u origin cbini/perf/claude-category-grades-daily-cron-rownum
```

Expected: the pre-push hook prints `No issues` and the branch is on origin.

- [ ] **Step 2: Open the PR**

Use `mcp__github__create_pull_request` with base `main`, head
`cbini/perf/claude-category-grades-daily-cron-rownum`, title
`perf(powerschool): build int_powerschool__category_grades once a day with a row_number section pick`.
Body follows `.github/pull_request_template.md`, keeping every template line,
with `Closes #5213` and these facts in the description: Newark 478 runs in 7
days at 26 slot-minutes each; every consumer is a daily batch (01:25 DeansList
extract, 04:00 Tableau and `int_students__category_grades`); the dedupe change
measured 12.1 to 3.2 slot-minutes with identical row count, grain, and grade
sums; dev build parity numbers from Task 1 Step 6. Write body paragraphs as
single lines (GitHub renders each newline). End with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

Read the returned title and body back and confirm they match.

- [ ] **Step 3: Comment the corrected diagnosis on #5213**

Use `mcp__github__add_issue_comment` on issue 5213 with one-line paragraphs:

```text
Re-ran the stage plan before starting. The join does not fan out: in the latest Newark run the storedgrades join took 6.89M rows in and put 6.89M out. The 142M-row read on that stage is BigQuery broadcasting the 1.3M-row storedgrades table to 100 workers, and the dedupe collapses the enrollment-by-termbin expansion by 13%.

What drives the 221 slot hours is cadence plus the dedupe shape. Newark rebuilt the table 478 times in 7 days (68 a day) on the eager table condition at 26 slot-minutes each. Every consumer is a daily batch (DeansList extract 01:25, Tableau gradebook batch and int_students__category_grades 04:00). The dbt_utils.deduplicate call compiles to 16 array_agg columns; a row_number pick over the same keys measured 3.2 slot-minutes against 12.1 with identical output.

Fix in PR <number>: midnight cron on the model and its pivot, row_number dedupe. Pre-aggregating storedgrades would not have moved the cost.
```

Replace `<number>` with the PR number from Step 2.

- [ ] **Step 4: Watch CI**

Invoke `pr-ci-review`. Expect `claude-review` and the kipptaf dbt Cloud CI job.
kipptaf CI will not build the package model; a green run only proves the kipptaf
wrappers still compile.

---

### Task 4: post-merge verification (after the first midnight tick)

**Files:** none.

- [ ] **Step 1: Confirm the run cadence dropped**

The morning after merge, run in the BigQuery MCP:

```sql
select
    regexp_extract(query, r'`teamster-332318`\.`([a-z_]+)`\.`int_powerschool__category_grades`') as dataset,
    count(*) as runs,
    round(sum(total_slot_ms) / 60000, 1) as slot_min
from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
where creation_time >= timestamp_sub(current_timestamp(), interval 1 day)
  and query like '%"node_id": "model.powerschool.int_powerschool__category_grades"%'
  and query like '%"target_name": "prod"%'
  and statement_type not like 'SC%'
group by 1
```

Expected: `runs` of 1 or 2 per dataset (the deploy rebuild plus the midnight
tick). More than 3 means the cron did not take; check the Dagster asset's
automation condition in the UI for `cron_tick_passed`.

- [ ] **Step 2: Re-run the parent ranking**

Run the ranking query from #5212 over 7 days once a full week has passed.
Expected: `model.powerschool.int_powerschool__category_grades` under 5 slot
hours. Report the number on #5212.
