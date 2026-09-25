# View Mart Table Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the 10 costliest view marts to cron-scheduled tables so their
dbt data tests read a table instead of recomputing the view, cutting about 610
slot hours a week.

**Architecture:** Each change is a `config:` block added to the model's
properties yml — `materialized: table` plus
`meta.dagster.automation_condition.cron_schedule`. No model SQL changes, so
surrogate-key hashes and row sets stay identical and the conversion is a pure
materialization change. A dev-schema build gates the merge on measured table
size. One ordered Dagster run finishes the migration post-merge.

**Tech Stack:** dbt 1.11.14 on BigQuery, Dagster+ automation conditions, trunk
(prettier + markdownlint + yamllint), `uv` for every Python and dbt invocation.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-11-view-mart-table-sweep-design.md`.
  Issue [#5217](https://github.com/TEAMSchools/teamster/issues/5217), parent
  [#5212](https://github.com/TEAMSchools/teamster/issues/5212).
- Worktree:
  `/workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep`.
  Branch `cbini/perf/claude-view-mart-table-sweep`. Every `git` call uses
  `git -C <worktree>`; every file path is absolute under the worktree.
- Never run bare `python`, `dbt`, or `dagster`. Always `uv run`.
- Do NOT change any model's `.sql` file. This plan touches properties yml only.
- Do NOT run `count(*)` against these views. One attempt over 4 of them consumed
  100,540 slot minutes and failed with `billingTierLimitExceeded`. Row counts
  come from `__TABLES__` on the dev dataset after a build.
- Do NOT pass `--empty` to any `dbt build`. It rebuilds every selected relation
  as `limit 0`, which would zero the dev tables this plan measures.
- `--target prod` dbt runs are classifier-blocked. Prod materialization happens
  through Dagster `launch_run`, or is handed to the user.
- The 7 no-consumer marts get `cron_schedule: 0 3 * * *`. The 3 Cube-read marts
  get `cron_schedule: 0 0,10,13,15,17 * * *`. These come from per-model
  break-even in the spec; do not substitute one cadence for both.
- All 10 already use `columns[].config.meta.foreign_key`, not real
  `constraints: - type: foreign_key`. Do not add or move FK constraints.
- Verified 2026-09-11: `git log -S` shows zero prior `materialized: table` or
  `cron_schedule` commits on all 10 files, so this is not a re-attempt of a
  reverted change.

---

### Task 1: Worktree prep and prod baseline

Establishes that dbt can run in this worktree at all, and records the
before-state that Task 6 verifies against. The worktree was created fresh, so it
has no `dbt_packages/` and every dbt command fails until `dbt deps` runs.

**Files:**

- Create:
  `/workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/docs/superpowers/plans/baseline-2026-09-11.md`

**Interfaces:**

- Consumes: nothing.
- Produces: `baseline-2026-09-11.md`, holding the prod object type of all 10
  marts before the change. Task 6 diffs against it.

- [ ] **Step 1: Install dbt packages in the worktree**

```bash
uv run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf
```

Expected: `Installing ...` lines, then `Installed from ...` for each package. A
fresh worktree has no `dbt_packages/`; without this every later command fails
with "N package(s) specified in packages.yml, but only 0 package(s) installed".

- [ ] **Step 2: Confirm the project parses before any edit**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf
```

Expected: exits 0. This is the clean-baseline parse — if it fails here, the
failure is pre-existing and not caused by this plan.

- [ ] **Step 3: Record the prod object type of all 10 marts**

Run this through the BigQuery MCP (`mcp__bigquery__execute_sql`):

```sql
select
  table_id,
  if(type = 1, 'TABLE', 'VIEW') as object_type,
  row_count,
  round(size_bytes / pow(1024, 3), 3) as size_gb,
  timestamp_millis(last_modified_time) as last_modified,
from `teamster-332318.kipptaf_marts.__TABLES__`
where
  table_id in (
    'bridge_survey_expectations',
    'fct_survey_submissions',
    'fct_student_attendance_daily',
    'fct_survey_responses',
    'dim_college_enrollments',
    'dim_survey_administrations',
    'fct_grades_assignments',
    'fct_support_tickets',
    'dim_staff_reporting_chain',
    'dim_staff_work_history'
  )
order by table_id
```

Expected: 10 rows, every one `VIEW`, `row_count` 0 and `size_gb` 0 (a view
stores nothing).

- [ ] **Step 4: Write the baseline file**

Write exactly this file, replacing each `VIEW` row's values with the query
output from Step 3:

```markdown
# View mart table sweep — baseline

Captured before the sweep. Refs
[#5217](https://github.com/TEAMSchools/teamster/issues/5217).

## Prod object types before the sweep

| mart                           | object type | row count | size GB |
| ------------------------------ | ----------- | --------: | ------: |
| `bridge_survey_expectations`   | VIEW        |         0 |       0 |
| `dim_college_enrollments`      | VIEW        |         0 |       0 |
| `dim_staff_reporting_chain`    | VIEW        |         0 |       0 |
| `dim_staff_work_history`       | VIEW        |         0 |       0 |
| `dim_survey_administrations`   | VIEW        |         0 |       0 |
| `fct_grades_assignments`       | VIEW        |         0 |       0 |
| `fct_student_attendance_daily` | VIEW        |         0 |       0 |
| `fct_support_tickets`          | VIEW        |         0 |       0 |
| `fct_survey_responses`         | VIEW        |         0 |       0 |
| `fct_survey_submissions`       | VIEW        |         0 |       0 |

## Dev build sizes

Filled by Task 4. A mart at 50 GB or more stops the merge and goes to the user.

| mart | dev rows | dev size GB | verdict |
| ---- | -------: | ----------: | ------- |
```

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep add docs/superpowers/plans/
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep commit -m "docs(superpowers): plan and baseline for the view mart table sweep

Refs #5217

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Convert the 7 marts with no live reader

These 7 have no `sql_table` pointing at them anywhere in `src/cube/model/` and
no Tableau exposure, so nothing reads them today. They take the nightly cadence,
which sits far below every one of their break-evens.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/bridges/properties/bridge_survey_expectations.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_submissions.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_support_tickets.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_survey_administrations.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_college_enrollments.yml`

All paths are relative to
`/workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/`.

**Interfaces:**

- Consumes: a parsing project from Task 1.
- Produces: 7 marts configured `materialized: table` with
  `cron_schedule: 0 3 * * *`, each with `warn_unenforced: false` on its
  `primary_key` constraint. Task 4 builds them.

- [ ] **Step 1: Add the config block to each of the 7 files**

In each file, insert this block immediately BEFORE the line `    columns:` (4
spaces of indent). The model-level key order the repo uses is `description:`,
then `config:`, then `columns:` — matching
`dimensions/properties/dim_assessments.yml`.

```yaml
config:
  materialized: table
  meta:
    dagster:
      # Nightly: every data test on this view recomputed it in full, and
      # dbt Cloud CI ran that on nearly every PR. No Cube cube or Tableau
      # exposure reads this mart, so nightly clears its break-even with
      # room to spare. Refs #5217
      automation_condition:
        cron_schedule: 0 3 * * *
```

Use Edit with `old_string` = `    columns:` and `new_string` = the block above
followed by `    columns:`. The first `    columns:` occurrence is the
model-level one in every file; confirm by checking the line number matches the
table below before editing.

| File                         | `    columns:` is at line |
| ---------------------------- | ------------------------: |
| `bridge_survey_expectations` |                        16 |
| `fct_survey_submissions`     |                        18 |
| `fct_survey_responses`       |                         9 |
| `dim_college_enrollments`    |                         9 |
| `dim_survey_administrations` |                         9 |
| `fct_grades_assignments`     |                        19 |
| `fct_support_tickets`        |                        12 |

- [ ] **Step 2: Add `warn_unenforced: false` to each primary key constraint**

A `config.materialized: table` mart renders its `constraints:` into the CREATE
TABLE DDL, and dbt warns on an unenforced constraint unless told not to. Each of
the 7 files has exactly one occurrence of this pair:

```yaml
constraints:
  - type: primary_key
    warn_unsupported: false
```

Change it to:

```yaml
constraints:
  - type: primary_key
    warn_unsupported: false
    warn_unenforced: false
```

Verify exactly one occurrence per file first:

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf/models/marts
grep -c 'type: primary_key' \
  bridges/properties/bridge_survey_expectations.yml \
  facts/properties/fct_survey_submissions.yml \
  facts/properties/fct_survey_responses.yml \
  facts/properties/fct_grades_assignments.yml \
  facts/properties/fct_support_tickets.yml \
  dimensions/properties/dim_survey_administrations.yml \
  dimensions/properties/dim_college_enrollments.yml
```

Expected: `1` for all 7 files.

- [ ] **Step 3: Verify the config landed on all 7**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf/models/marts
grep -l 'cron_schedule: 0 3 \* \* \*' */properties/*.yml | sort
```

Expected: exactly these 7 paths, and no others:

```text
bridges/properties/bridge_survey_expectations.yml
dimensions/properties/dim_college_enrollments.yml
dimensions/properties/dim_survey_administrations.yml
facts/properties/fct_grades_assignments.yml
facts/properties/fct_support_tickets.yml
facts/properties/fct_survey_responses.yml
facts/properties/fct_survey_submissions.yml
```

- [ ] **Step 4: Parse to prove the YAML is valid and the config is picked up**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf
```

Expected: exits 0. A YAML indentation error in the inserted block fails here
with a parse error naming the file.

- [ ] **Step 5: Confirm dbt resolved the materialization, not just the YAML**

```bash
uv run dbt ls --resource-type model --output json \
  --select bridge_survey_expectations fct_survey_submissions fct_survey_responses \
    fct_grades_assignments fct_support_tickets dim_survey_administrations \
    dim_college_enrollments \
  --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf \
  2>/dev/null | grep '^{' | uv run python -c \
  "import sys, json; [print(json.loads(line)['name'], json.loads(line)['config']['materialized']) for line in sys.stdin]"
```

Expected: 7 lines, each ending in `table`. `dbt ls --output json` interleaves
log lines with JSON records, which is why the output is filtered through
`grep '^{'`.

- [ ] **Step 6: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/marts/bridges/properties/bridge_survey_expectations.yml \
  src/dbt/kipptaf/models/marts/facts/properties/fct_survey_submissions.yml \
  src/dbt/kipptaf/models/marts/facts/properties/fct_survey_responses.yml \
  src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml \
  src/dbt/kipptaf/models/marts/facts/properties/fct_support_tickets.yml \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_survey_administrations.yml \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_college_enrollments.yml \
  </dev/null
```

Expected: `✔ No issues`. If prettier reports "Incorrect formatting", run
`/workspaces/teamster/.trunk/tools/trunk fmt <same files> </dev/null` and re-run
the check.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep add -u
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep commit -m "perf(dbt): materialize the 7 unread survey and grades marts as nightly tables

Every data test on a view mart recomputes the view. These 7 have no Cube or
Tableau reader, so nightly clears each one's break-even.

Refs #5217

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Convert the 3 marts Cube reads

These 3 have live readers, so they take the intraday tick the assessment marts
already use. `fct_student_attendance_daily` anchors topline Total Enrollment;
`dim_staff_reporting_chain` is queried once per Cube user session to build the
PII access scope; `dim_staff_work_history` backs the `staff_work_history` cube.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_daily.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_history.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_chain.yml`

**Interfaces:**

- Consumes: a parsing project from Task 2.
- Produces: 3 marts configured `materialized: table` with
  `cron_schedule: 0 0,10,13,15,17 * * *`. Task 4 builds all 10 together.

- [ ] **Step 1: Add the config block to `fct_student_attendance_daily.yml`**

Insert immediately BEFORE the line `    columns:` at line 28:

```yaml
config:
  materialized: table
  meta:
    dagster:
      # 5x/day, matching the assessment marts. Cube's student_enrollments
      # and student_attendance cubes read this mart and anchor topline
      # Total Enrollment, so it needs the intraday tick. That is above its
      # own break-even (prod 1.7 to 7.9 slot hours a week), accepted
      # because the CI column drops 90.5 to about 21. Refs #5217
      automation_condition:
        cron_schedule: 0 0,10,13,15,17 * * *
```

- [ ] **Step 2: Add the config block to `dim_staff_work_history.yml`**

This file has a model-level `data_tests:` at line 9 and no `config:` block.
Insert immediately BEFORE the line `    data_tests:`, so the key order stays
`description:`, `config:`, `data_tests:`, `columns:`:

```yaml
config:
  materialized: table
  meta:
    dagster:
      # 5x/day, matching the assessment marts. The staff_work_history cube
      # reads this mart. Refs #5217
      automation_condition:
        cron_schedule: 0 0,10,13,15,17 * * *
```

- [ ] **Step 3: Extend the EXISTING config block in
      `dim_staff_reporting_chain.yml`**

This file already has a `config:` block at line 21 carrying
`contract: enforced: false`. Do NOT add a second `config:` key — a duplicate
mapping key is invalid YAML. Edit the existing block.

Replace:

```yaml
config:
  # WITH RECURSIVE is incompatible with the contract-validation subquery
  # wrapper; orphan detection is preserved via the relationships tests below.
  contract:
    enforced: false
```

With:

```yaml
config:
  materialized: table
  # WITH RECURSIVE is incompatible with the contract-validation subquery
  # wrapper; orphan detection is preserved via the relationships tests below.
  # The CTAS wrapper is fine with recursion — int_illuminate__root_standards
  # is WITH RECURSIVE plus materialized: table in prod.
  contract:
    enforced: false
  meta:
    dagster:
      # 5x/day, matching the assessment marts. cube.js queries this mart
      # once per user session to build the PII access scope, at 16.1 slot
      # minutes a call as a view. Refs #5217
      automation_condition:
        cron_schedule: 0 0,10,13,15,17 * * *
```

- [ ] **Step 4: Add `warn_unenforced: false` where a primary key constraint
      exists**

`fct_student_attendance_daily.yml` and `dim_staff_work_history.yml` each have
exactly one `- type: primary_key` block. Change each from:

```yaml
constraints:
  - type: primary_key
    warn_unsupported: false
```

to:

```yaml
constraints:
  - type: primary_key
    warn_unsupported: false
    warn_unenforced: false
```

`dim_staff_reporting_chain.yml` has NO `primary_key` constraint — it uses a
model-level `dbt_utils.unique_combination_of_columns` on
`(manager_staff_key, reportee_staff_key)` instead. Do not add a constraint to
it. Confirm:

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf/models/marts
grep -c 'type: primary_key' \
  facts/properties/fct_student_attendance_daily.yml \
  dimensions/properties/dim_staff_work_history.yml \
  dimensions/properties/dim_staff_reporting_chain.yml
```

Expected: `1`, `1`, `0` in that order.

- [ ] **Step 5: Verify all 10 marts now carry a cron, and no others changed**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf/models/marts
grep -l 'materialized: table' */properties/*.yml | sort
```

Expected: 21 paths — the 11 that were already tables (`dim_assessments`,
`dim_assessment_administrations`, `dim_courses`, `dim_dates`, `dim_regions`,
`dim_staff`, `dim_students`, `bridge_assessment_expectations_enrollment_scoped`,
`bridge_assessment_expectations_student_scoped`,
`fct_assessment_scores_enrollment_scoped`,
`fct_assessment_scores_student_scoped`) plus the 10 from Tasks 2 and 3.

- [ ] **Step 6: Parse**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf
```

Expected: exits 0. A duplicate `config:` key in `dim_staff_reporting_chain.yml`
fails here — that is the specific mistake Step 3 guards against.

- [ ] **Step 7: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_daily.yml \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_history.yml \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_chain.yml \
  </dev/null
```

Expected: `✔ No issues`.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep add -u
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep commit -m "perf(dbt): materialize the 3 Cube-read marts on the assessment tick

Cube reads all 3, so they take the intraday cadence rather than nightly.
cube.js queries dim_staff_reporting_chain once per user session, which as a
view recomputed a recursive closure at 16.1 slot minutes a call.

Refs #5217

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Sizing gate — build all 10 into the dev schema and measure

This is the merge gate. `bridge_survey_expectations` is a scaffold with a
`cross join` to every contact person: as a view that costs compute, as a table
it costs storage permanently. Nothing merges until each table's real size is on
record.

**Files:**

- Modify: `docs/superpowers/plans/baseline-2026-09-11.md` (fill the
  `## Dev build sizes` table)

**Interfaces:**

- Consumes: the 10 configured marts from Tasks 2 and 3.
- Produces: a row count and byte size per mart, and a go or no-go per mart.

- [ ] **Step 1: Build all 10 into the dev schema**

```bash
uv run dbt build \
  --select bridge_survey_expectations fct_survey_submissions fct_survey_responses \
    fct_grades_assignments fct_support_tickets dim_survey_administrations \
    dim_college_enrollments fct_student_attendance_daily dim_staff_work_history \
    dim_staff_reporting_chain \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep/src/dbt/kipptaf
```

4 things about this command:

1. `--state` is ABSOLUTE and points at the MAIN checkout. The relative form
   resolves under the worktree, which has no `target/prod/`, and fails with
   "Could not find manifest".
2. `--favor-state` resolves every unselected upstream to prod, so a stale
   personal dev copy cannot shadow the build.
3. No `--empty`. It would rebuild each selected relation as `limit 0` and the
   Step 3 measurement would read 0 rows.
4. This build costs roughly 2.5 slot hours in total. That is expected — it is
   one full computation of each view, which is exactly the number being
   measured.

Expected: `Completed successfully`, with `CREATE TABLE` (not `CREATE VIEW`) in
each model's log line. A data test that fails here is diagnostic, not blocking —
record it and continue to Step 2. The marts `foreign_key` deferral trap does not
apply: none of the 10 carries a real FK constraint.

- [ ] **Step 2: Find the dev dataset the build actually wrote to**

```sql
select schema_name
from `teamster-332318`.INFORMATION_SCHEMA.SCHEMATA
where schema_name like 'zz_%kipptaf_marts'
```

Expected: `zz_cbini_kipptaf_marts`. Local dev builds land in
`zz_<GITHUB_USER>_<project>_<schema>`, not the shipped `zz_dagster_*` schema.
Use whatever this query returns in Step 3.

- [ ] **Step 3: Measure row count and size**

```sql
select
  table_id,
  if(type = 1, 'TABLE', 'VIEW') as object_type,
  row_count,
  round(size_bytes / pow(1024, 3), 3) as size_gb,
from `teamster-332318.zz_cbini_kipptaf_marts.__TABLES__`
where
  table_id in (
    'bridge_survey_expectations',
    'fct_survey_submissions',
    'fct_student_attendance_daily',
    'fct_survey_responses',
    'dim_college_enrollments',
    'dim_survey_administrations',
    'fct_grades_assignments',
    'fct_support_tickets',
    'dim_staff_reporting_chain',
    'dim_staff_work_history'
  )
order by size_gb desc
```

Expected: 10 rows, every `object_type` = `TABLE`. Any row still reading `VIEW`
means that model's `materialized: table` did not take — go back to Task 2 or 3
for it.

`__TABLES__.row_count` can lag and read 0 right after a build. If any row reads
0, re-run this query once before treating it as real. Do NOT fall back to
`count(*)` on the prod view; if a dev count is genuinely needed, run
`select count(*) from zz_cbini_kipptaf_marts.<model>` against the dev TABLE,
which is cheap because it is a table.

- [ ] **Step 4: Apply the go or no-go rule per mart**

Record every result. Then, for each mart:

- Under 50 GB: proceed.
- 50 GB or more: stop and report that mart to the user before merging. Do not
  silently drop it — name it, give its size, and ask whether to keep it as a
  view. `bridge_survey_expectations` is the one most likely to trip this.

- [ ] **Step 5: Fill in the baseline file and commit**

Write the 10 measured rows into the `## Dev build sizes` table in
`docs/superpowers/plans/baseline-2026-09-11.md`, then:

```bash
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep add -u
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep commit -m "docs(superpowers): record dev build sizes for the 10 converted marts

Refs #5217

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Push, open the pull request, and clear CI

**Files:**

- Create: nothing. This task pushes Tasks 1 through 4.

**Interfaces:**

- Consumes: 4 commits on `cbini/perf/claude-view-mart-table-sweep`.
- Produces: an open PR with green dbt Cloud CI.

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/perf/claude-view-mart-table-sweep push
```

The branch already tracks `origin/cbini/perf/claude-view-mart-table-sweep` from
`gh issue develop`, so a bare `push` is correct here.

- [ ] **Step 2: Open the PR**

Use `mcp__github__create_pull_request` with `base: main`,
`head: cbini/perf/claude-view-mart-table-sweep`, and title
`perf(dbt): materialize the 10 costliest view marts as cron tables`.

The body below keeps every line `.github/pull_request_template.md` supplies and
answers its prompts in place, per that template's own instruction. Do not
hard-wrap it — GitHub renders every newline as a line break. Do NOT
`gh project item-add` the PR; the `Closes #5217` ref puts it on the board.

Fill the 3 bracketed values from Task 4's measurements before posting.

```markdown
## Summary & Motivation

When merged, this pull request will make 10 dbt marts build as tables on a cron
schedule instead of as views.

Every data test on a view mart recomputes that whole view before it can check
anything. These 10 marts cost 936 slot hours a week that way, which is 32% of
all warehouse compute in the project. As tables, their tests read a table
instead.

Expected result: prod drops from 94 to 38 slot hours a week, and dbt Cloud CI
from 818 to about 263. That is about 610 slot hours a week.

No model SQL changes, so surrogate keys and row sets stay identical.

## Reviewer Notes

`fct_student_attendance_daily` knowingly costs more in prod, 1.7 to 7.9 slot
hours a week. Cube's enrollment count reads it and needs the 5x/day tick, which
is above its own break-even. Its CI column drops 90.5 to about 21, so it still
wins overall.

The 2 cadences are derived, not picked. The 7 marts with no Cube or Tableau
reader get `0 3 * * *`. The 3 Cube reads get `0 0,10,13,15,17 * * *`, the same
tick the assessment marts use.

`dim_staff_reporting_chain` uses `WITH RECURSIVE`. That is fine in a table —
`int_illuminate__root_standards` already ships as `WITH RECURSIVE` plus
`materialized: table`.

Largest new table: [NAME] at [N] GB, [N] rows. Full sizes in
`docs/superpowers/plans/baseline-2026-09-11.md`.

This migration needs one ordered Dagster run after merge, selecting all 10
assets together. A config-only yml change does not bump `code_version`, so the
sensor will not pick these up on its own, and view to table drops the view
before it creates the table.

## Self-review

### General

- [x] Update **due date** and **assignee** on the
      [TEAMster Asana Project](https://app.asana.com/0/1205971774138578/1205971926225838)
- [ ] Review the **Claude Code Review** comment posted on this PR. Address valid
      feedback; dismiss false positives with a brief reply explaining why.
      (Claude is advisory — use your judgement, but don't ignore it.)

### Dagster _(skip if no Dagster changes)_

No Dagster code changes. The cron cadences are dbt `meta.dagster` config read by
the existing translator.

### dbt _(skip if no dbt changes)_

- [x] Include a `[model_name].yml` properties file for all new models — see
      [dbt Conventions](https://teamschools.github.io/teamster/reference/dbt-conventions/#model-properties-file)
- [x] Include (or update) an
      [exposure](https://teamschools.github.io/teamster/reference/dbt-conventions/#exposures)
      for all models consumed by a dashboard, analysis, or application
- [x] **Breaking change?** No columns renamed or removed. Materialization only.
- [x] If adding or modifying an external source, run `stage_external_sources`
      with **`--target staging`** so the dbt Cloud CI job can find the table. No
      external sources touched.

### Docs _(skip if no schedule, sensor, or integration changes)_

No schedule or sensor added. Automation conditions on dbt models are not in the
automations catalog.

## CI checks

- [ ] **Trunk** — passes.
- [ ] **dbt Cloud** — passes.
- [ ] **Dagster Cloud** — passes or not triggered.

Closes #5217

<details>
<summary>For Claude</summary>

Claude-assisted, human-directed. Design doc:
`docs/superpowers/specs/2026-09-11-view-mart-table-sweep-design.md`. Plan:
`docs/superpowers/plans/2026-09-11-view-mart-table-sweep.md`.

Two mechanisms drove the cost, and the table conversion fixes both. CI's
`state:modified+` pulls these marts into nearly every PR, which is 818 of the
936 hours. In prod the child views never rebuild at all, yet their tests run 128
times a week each, because dbt's default `--indirect-selection=eager` selects a
test when ANY parent is selected and `dim_staff` rebuilds 192 times a week.

Setting `--indirect-selection=cautious` at
`src/teamster/libraries/dbt/assets.py:112` was considered and rejected. It would
remove 72.3 of the 117.5 weekly prod test slot hours, but it does nothing for
CI, it is repo-wide across all 5 code locations, and it trades away parent-side
FK orphan detection on every view mart.

All 10 already declared FKs as `config.meta.foreign_key`, not real
`constraints`, so the #4821 migration needed no work here. `git log -S`
confirmed zero prior `materialized: table` or `cron_schedule` commits on all 10,
so this is not a re-attempt of the #4464 change that #4587 reverted.

Do not run `count(*)` against these views. One attempt over 4 of them consumed
100,540 slot minutes and failed with `billingTierLimitExceeded`.

</details>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 3: Watch dbt Cloud CI**

```bash
gh pr checks <PR_NUMBER> --json name,bucket,state
```

Expected: all buckets `pass`. CI runs
`dbt build --select state:modified+ --full-refresh` against `target: staging`.

This PR modifies 10 marts, so `state:modified+` will pull in their whole
descendant graph. Per `src/dbt/kipptaf/CLAUDE.md`, expect latent
`severity: error` failures unrelated to this change on models CI has never
built. Before assuming this change caused one, query prod for the same
condition.

- [ ] **Step 4: Confirm CI built them as tables, not views**

```sql
select table_name, table_type
from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.TABLES
where
  table_schema like 'dbt_cloud_pr_%_marts'
  and table_name in (
    'bridge_survey_expectations',
    'fct_survey_submissions',
    'fct_student_attendance_daily',
    'fct_survey_responses',
    'dim_college_enrollments',
    'dim_survey_administrations',
    'fct_grades_assignments',
    'fct_support_tickets',
    'dim_staff_reporting_chain',
    'dim_staff_work_history'
  )
```

Expected: 10 rows, every `table_type` = `BASE TABLE`.

- [ ] **Step 5: Process review findings**

If `claude-review` posts findings, invoke `superpowers:receiving-code-review`
before acting on them, and post a per-finding verdict as a PR comment. For
everything else about CI and review, invoke `pr-ci-review`.

---

### Task 6: Finish the prod migration with one ordered run

This is the step that #4464 got wrong and #4587 reverted. A config-only
properties yml change does not bump `code_version` (a SHA1 of raw SQL), so the
automation sensor never selects these models on deploy. View to table also DROPS
the view before it creates the table, so leaving it to the sensor leaves
relations MISSING from prod rather than stale.

Do not start this task until the PR is squash-merged to `main`.

**Files:**

- Create: nothing. This task runs against prod through Dagster.

**Interfaces:**

- Consumes: the merged change on `main`.
- Produces: all 10 relations existing in `kipptaf_marts` as tables.

- [ ] **Step 1: Confirm the merge deployed**

```bash
gh run list --workflow deploy-prod-kipptaf.yaml --limit 3
```

Expected: the most recent run for the merge commit shows `completed success`.
The Dagster code location must reload before it knows these are table assets.

- [ ] **Step 2: Preview the run**

Use `mcp__dagster__launch_run` with `confirm=False` first. Every Dagster
mutation tool previews on `confirm=False` and only executes on `confirm=True`.

Select all 10 assets in ONE run:

```text
kipptaf/marts/bridge_survey_expectations
kipptaf/marts/fct_survey_submissions
kipptaf/marts/fct_survey_responses
kipptaf/marts/fct_grades_assignments
kipptaf/marts/fct_support_tickets
kipptaf/marts/dim_survey_administrations
kipptaf/marts/dim_college_enrollments
kipptaf/marts/fct_student_attendance_daily
kipptaf/marts/dim_staff_work_history
kipptaf/marts/dim_staff_reporting_chain
```

This key format is verified: `mcp__dagster__search_assets` with
`prefix: kipptaf/marts` returns keys shaped
`["kipptaf", "marts", "<model_name>"]`.

One run is one `dbt build`, which dbt topologically sorts — that ordering is the
whole point of this task. Ten separate runs would reproduce the #4464 failure.

Each asset also carries a `dagster/materialized` tag whose value is `view` or
`table`. Before launching, run `mcp__dagster__search_assets` with
`prefix: kipptaf/marts` and confirm all 10 already read `table` — that proves
the code location reloaded with the merged config. If any still reads `view`,
the deploy in Step 1 has not taken effect yet; wait and re-check rather than
launching.

- [ ] **Step 3: Launch the run**

Re-issue the same `mcp__dagster__launch_run` call with `confirm=True`.

- [ ] **Step 4: Verify every relation exists and is a table**

```sql
select
  table_id,
  if(type = 1, 'TABLE', 'VIEW') as object_type,
  row_count,
  round(size_bytes / pow(1024, 3), 3) as size_gb,
  timestamp_millis(last_modified_time) as last_modified,
from `teamster-332318.kipptaf_marts.__TABLES__`
where
  table_id in (
    'bridge_survey_expectations',
    'fct_survey_submissions',
    'fct_student_attendance_daily',
    'fct_survey_responses',
    'dim_college_enrollments',
    'dim_survey_administrations',
    'fct_grades_assignments',
    'fct_support_tickets',
    'dim_staff_reporting_chain',
    'dim_staff_work_history'
  )
order by table_id
```

Expected: 10 rows, every `object_type` = `TABLE`, every `last_modified` from
this run, and `row_count` matching Task 4's dev measurement within normal daily
drift.

A mart MISSING from this result is the #4464 failure signature — absence, not
staleness. If any is missing, re-run Step 3 selecting only the missing assets
and read the run logs with `mcp__dagster__get_run_logs`.

- [ ] **Step 5: Confirm Cube's PII scope still resolves**

`src/cube/cube.js:145` runs this per user session. Run it against a manager who
is known to have direct reports:

```sql
select count(*) as n_reportees
from `teamster-332318.kipptaf_marts.dim_staff_reporting_chain`
where manager_staff_key = @k
```

Pick `@k` by taking any `manager_staff_key` that appears with more than 1
distinct `reportee_staff_key`. Expected: a non-zero count. A zero here means
Cube denies that manager PII access as if they had no downline.

- [ ] **Step 6: Measure the result after 7 days**

Do not run this immediately — it needs a full week of prod and CI activity to
compare against the spec's projection.

```sql
with names as (
  select
    [
      'bridge_survey_expectations', 'fct_survey_submissions',
      'fct_student_attendance_daily', 'fct_survey_responses',
      'dim_college_enrollments', 'dim_survey_administrations',
      'fct_grades_assignments', 'fct_support_tickets',
      'dim_staff_reporting_chain', 'dim_staff_work_history'
    ] as arr
),
j as (
  select
    regexp_replace(
      regexp_replace(
        json_value(
          regexp_extract(query, r'^/\* (\{.*?\}) \*/'), '$.node_id'
        ),
        r'^test\.kipptaf\.', ''
      ),
      r'__ref_.*$', ''
    ) as tname,
    json_value(
      regexp_extract(query, r'^/\* (\{.*?\}) \*/'), '$.target_name'
    ) as target,
    total_slot_ms,
  from `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
  where
    creation_time >= timestamp_sub(current_timestamp(), interval 7 day)
    and query like '%"node_id"%'
    and total_slot_ms > 0
)
select
  (
    select n
    from unnest(names.arr) as n with offset o
    where strpos(j.tname, n) > 0
    order by o
    limit 1
  ) as mart,
  round(sum(if(target = 'prod', total_slot_ms, 0)) / 1000 / 60 / 60, 1) as prod_hr,
  round(
    sum(if(target = 'staging', total_slot_ms, 0)) / 1000 / 60 / 60, 1
  ) as ci_hr,
from j
cross join names
group by mart
having mart is not null
order by prod_hr + ci_hr desc
```

Expected: prod near 38 and CI near 263 slot hours, against 94 and 818 before.
The `__ref_.*$` strip is required — without it a `relationships` test is
attributed to its FK target instead of the mart it tests.

Post the result as a comment on issue
[#5212](https://github.com/TEAMSchools/teamster/issues/5212), the parent issue
tracking warehouse slot time.
