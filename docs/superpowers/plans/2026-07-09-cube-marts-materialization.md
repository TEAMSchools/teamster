# Cube marts materialization (#4333) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the assessment Cube queries timing out cold by materializing the
75 Cube-read marts as tables (from views), with an optional pre-aggregation on
the assessment hot path decided by measurement.

**Architecture:** Three additive layers — (1) flip the `marts:` dbt default from
`view` to `table` so Cube reads static tables instead of re-expanding a 2.85 GB
multi-join view per query (the root-cause fix); (2) full-refresh tables, no
incremental this cycle; (3) a conditional `rollup` pre-aggregation on the
assessment cube, shipped only if a measured cost/benefit justifies it.

**Tech Stack:** dbt (BigQuery), Cube semantic layer (`cube.js` + YAML), Cube SQL
API (Postgres wire) via `psycopg2`, BigQuery MCP for build-stat inspection.

**Spec:**
`docs/superpowers/specs/2026-07-09-cube-marts-materialization-design.md`

## Global Constraints

- **Branch:** `cristinabaldor/fix/claude-cube-marts-materialization`, stacked on
  `cristinabaldor/feat/claude-cube-security-redesign` (PR #4269, still open).
  Retarget the PR to `main` when #4269 merges.
- **No prod dbt runs from Claude.** `--target prod` `dbt build`/`run` and
  `stage_external_sources --target staging` are classifier-blocked — hand prod
  runs to the user. Local validation is
  `--target dev --defer --state src/dbt/kipptaf/target/prod` (or
  `--target staging`). `dbt parse`/`compile --target prod` are allowed (no
  warehouse write).
- **Dev-schema redirects are uncommittable.** When redirecting a cube
  `sql_table` or `cube.js` read to `zz_<user>_kipptaf_marts`, never `git add`
  the whole `src/cube/` dir; name files explicitly, and `grep -r zz_ src/cube`
  before every commit (must be empty).
- **PII stays local.** No PII values in commits, PR text, or any external
  surface. The assessment summary view is aggregate-only, but connection emails
  / student rows from local validation stay in `.claude/scratch/`.
- **Cube conventions:** cubes `public: false`; pre-aggregations live on the
  cube, not the view; `sql_table` points at `kipptaf_marts.<table>`.
- **Table-mart constraints:** every table-mart PK/constraint that has
  `warn_unsupported: false` also needs `warn_unenforced: false` once the mart is
  a table, or `dbt parse` warns.
- **Lint before push:** `.trunk/tools/trunk check --force <files>` on every
  changed `.md` / `.yml` / `.sql` (markdownlint + sqlfluff + yamllint fire at
  pre-push/CI, not the commit hook).
- **The user starts the Cube dev server** (long-running; Claude cannot). The VS
  Code task is `Cube: Dev Server`. Ask and wait when a task needs it.

---

## File structure

| File                                                                               | Responsibility                                           | Task |
| ---------------------------------------------------------------------------------- | -------------------------------------------------------- | ---- |
| `.claude/scratch/measure_cube_sql.py`                                              | psycopg2 SQL-API latency + BQ-stat harness (uncommitted) | 1    |
| `src/dbt/kipptaf/dbt_project.yml`                                                  | flip `marts:` default to `+materialized: table`          | 3    |
| `src/dbt/kipptaf/models/marts/**/properties/*.yml`                                 | add `warn_unenforced: false` to table-mart constraints   | 3    |
| `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_chain.yml` | possible `materialized: view` override (WITH RECURSIVE)  | 3    |
| `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`           | conditional `pre_aggregations` block                     | 4    |
| `src/cube/CLAUDE.md`, `src/dbt/kipptaf/models/marts/CLAUDE.md`                     | doc updates if conventions shift                         | 5    |

---

## Task 1: Spike A — prove table beats view over the SQL API (scenario B)

Validates the whole approach before any committed config change. Deliverable is
a recorded measurement, not code — the dev-schema build and redirects are
uncommittable scaffold.

**Files:**

- Create (uncommitted): `.claude/scratch/measure_cube_sql.py`
- Temporarily modify (revert before end of task):
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`
  (`sql_table` → dev schema), and the `cube.js` identity reads + `loadUniverses`
  department query → `zz_<user>_kipptaf_marts`.

**Interfaces:**

- Produces: measured cold latency + BQ `total_bytes_processed` / `total_slot_ms`
  for scenario **B** (assessment fact materialized as a table), compared against
  the recorded **A** baseline (65.5 s cold). Gate for Task 3.

- [ ] **Step 1: Build the assessment fact + its dims as tables in your dev
      schema**

`dim_dates` is already a table; build the fact and the dims the summary view
joins, materialized as tables, into `zz_<user>_kipptaf_marts`:

```bash
uv run dbt build \
  --select fct_assessment_scores_enrollment_scoped \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state src/dbt/kipptaf/target/prod \
  --vars '{}' \
  --full-refresh
```

Force `table` for this dev build by adding a temporary
`config: materialized: table` to
`src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`
(revert in Step 8). Confirm the dev relation is a TABLE:

```sql
SELECT table_name, table_type
FROM `teamster-332318.zz_<user>_kipptaf_marts.INFORMATION_SCHEMA.TABLES`
WHERE table_name = 'fct_assessment_scores_enrollment_scoped'
```

Expected: `table_type = 'BASE TABLE'`.

- [ ] **Step 2: Stand up the dev-schema RLS scaffold**

Per `src/cube/CLAUDE.md` "Testing row-level security locally":

- Redirect the assessment cube's `sql_table` to
  `zz_<user>_kipptaf_marts.fct_assessment_scores_enrollment_scoped`.
- Redirect `cube.js`'s `resolveAccess` reads of `dim_staff_cube_access` /
  `dim_staff_reporting_chain` and `loadUniverses`' department query to
  `zz_<user>_kipptaf_marts` (the security branch reworked these; prod fails
  closed). Build those two dims to your dev schema first if not present.
- Comment out `CUBE_GROUP_MAP` in `.env` (its placeholder groups deny
  everything).

- [ ] **Step 3: Ask the user to start the Cube dev server**

Say: "Start the `Cube: Dev Server` VS Code task and confirm it's up." Wait for
confirmation. Note the `CUBEJS_PG_SQL_PORT`, `CUBEJS_SQL_USER`,
`CUBEJS_SQL_PASSWORD` from `src/cube/.env` (ask the user to read `.env` — it is
hook-blocked from Claude).

- [ ] **Step 4: Write the measurement harness**

```python
# .claude/scratch/measure_cube_sql.py  (uncommitted)
import statistics
import sys
import time

import psycopg2

VIEWER = sys.argv[1]  # a network-scope viewer email, e.g. cbaldor@apps.teamschools.org
PORT = int(sys.argv[2])
PASSWORD = sys.argv[3]

# The #4298 repro: count_scores by academic_year, filtered module_code = QA1.
QUERY = """
SELECT academic_year, MEASURE(count_scores) AS count_scores
FROM student_assessment_scores_summary
WHERE module_code = 'QA1'
GROUP BY 1
ORDER BY 1
"""


def run_once():
    conn = psycopg2.connect(
        host="127.0.0.1", port=PORT, user=VIEWER, password=PASSWORD, dbname="cube"
    )
    conn.autocommit = True
    t0 = time.monotonic()
    with conn.cursor() as cur:
        cur.execute(QUERY)
        rows = cur.fetchall()
    dt = time.monotonic() - t0
    conn.close()
    return dt, len(rows)


timings = []
for i in range(3):
    dt, n = run_once()
    print(f"run {i + 1}: {dt:.1f}s, {n} rows")
    timings.append(dt)
print(f"median: {statistics.median(timings):.1f}s")
```

- [ ] **Step 5: Run it COLD and record the median**

A fresh Cube dev-server start (or restart) gives a cold result cache; the first
of the 3 runs is the cold number, the rest are warm (informational).

```bash
uv run --with psycopg2-binary python .claude/scratch/measure_cube_sql.py \
  <viewer-email> <port> <password>
```

Record: cold (run 1) and warm (median of 2-3). **A = 65.5 s (baseline, view).**

- [ ] **Step 6: Capture the underlying BQ job stats**

Ask the user for the Cube dev-server log line showing the compiled BigQuery SQL
for the query (Dev Mode surfaces `console.log`/SQL in the playground logs
panel), or read the most recent assessment-fact query from
`INFORMATION_SCHEMA.JOBS`:

```sql
SELECT job_id, total_bytes_processed, total_slot_ms, creation_time
FROM `teamster-332318`.`region-us`.INFORMATION_SCHEMA.JOBS
WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 20 MINUTE)
  AND REGEXP_CONTAINS(query, 'fct_assessment_scores_enrollment_scoped')
ORDER BY creation_time DESC
LIMIT 5
```

Record `total_bytes_processed` / `total_slot_ms` for B.

- [ ] **Step 7: Evaluate the gate**

Compare B (table) against A (65.5 s). Expected: B well under 55 s (static table
read vs view re-expansion). **If B ≥ 55 s, STOP** — table conversion alone does
not fix #4333; report and rethink before Task 3.

- [ ] **Step 8: Revert all scaffold and confirm clean**

Revert the `sql_table` redirect, the `cube.js` redirects, the temporary
`materialized: table` on the fact yml, and un-comment `CUBE_GROUP_MAP` if you
changed it.

```bash
grep -r "zz_" src/cube/ && echo "STILL REDIRECTED — fix" || echo "clean"
git status --short
```

Expected: `clean`; `git status` shows no `src/cube/` or dbt changes. No commit
for this task (spike produces knowledge). Record A/B numbers in the PR
description draft (`.claude/scratch/`) for Task 5.

---

## Task 2: (removed — folded into Task 1 and Task 3)

Spike A (Task 1) is the pre-commit proof; the committed materialization change
is Task 3.

---

## Task 3: Flip marts to table + `warn_unenforced` sweep + WITH RECURSIVE check

The committable materialization change. This is the fix for #4333.

**Files:**

- Modify: `src/dbt/kipptaf/dbt_project.yml` (marts block, lines 199-202)
- Modify: `src/dbt/kipptaf/models/marts/**/properties/*.yml` (constraint sweep)
- Possibly modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_reporting_chain.yml`

**Interfaces:**

- Consumes: Task 1's gate (B < 55 s).
- Produces: all 75 Cube-read marts materialized as tables; `dbt parse` clean of
  `warn_unenforced` warnings; `dim_staff_reporting_chain` either a table or a
  documented view override.

- [ ] **Step 1: Flip the marts default to table**

Edit `src/dbt/kipptaf/dbt_project.yml`, the `marts:` block:

```yaml
marts:
  +schema: marts
  +materialized: table
  +contract:
    enforced: true
```

- [ ] **Step 2: Run parse to surface the `warn_unenforced` warnings**

```bash
uv run dbt parse --no-partial-parse --project-dir src/dbt/kipptaf --target prod \
  2>&1 | grep -i 'unenforced\|constraint' | sort -u
```

Expected: one warning per table-mart constraint lacking `warn_unenforced: false`
(the codebase currently has 78 files with `warn_unsupported: false` and only 1
with `warn_unenforced: false`).

- [ ] **Step 3: Sweep `warn_unenforced: false` next to every
      `warn_unsupported: false`**

For every constraint block flagged in Step 2, add `warn_unenforced: false` on
the line after `warn_unsupported: false`. Example
(`fct_assessment_scores_enrollment_scoped.yml`):

```yaml
constraints:
  - type: primary_key
    warn_unsupported: false
    warn_unenforced: false
```

Apply across all flagged `marts/**/properties/*.yml`. (A scripted pass:
`grep -rl 'warn_unsupported: false' src/dbt/kipptaf/models/marts/` gives the
file list; add the sibling line under each occurrence. Verify by re-parsing.)

- [ ] **Step 4: Re-parse; expect zero constraint warnings**

```bash
uv run dbt parse --no-partial-parse --project-dir src/dbt/kipptaf --target prod \
  2>&1 | grep -i 'unenforced' | sort -u
```

Expected: no output.

- [ ] **Step 5: Verify `dim_staff_reporting_chain` materializes as a table**

Build it to your dev schema as a table and confirm it succeeds (WITH RECURSIVE
CTAS may hit "WITH RECURSIVE is only allowed at the top level" if dbt wraps the
SQL):

```bash
uv run dbt build --select dim_staff_reporting_chain \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state src/dbt/kipptaf/target/prod --full-refresh 2>&1 | tail -20
```

Expected: SUCCESS. If it FAILS with a WITH RECURSIVE / top-level error, override
that one model back to view — add to its properties yml:

```yaml
config:
  materialized: view
```

and add an inline SQL comment at the top of `dim_staff_reporting_chain.sql`
noting the table CTAS breaks WITH RECURSIVE, so it stays a view.

- [ ] **Step 6: Build the assessment fact first (acute fix), then a broad dev
      sample**

```bash
uv run dbt build --select fct_assessment_scores_enrollment_scoped \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state src/dbt/kipptaf/target/prod --full-refresh 2>&1 | tail -20
```

Expected: SUCCESS; contract + `unique`/`not_null` tests pass. (The full 75-mart
`--full-refresh` build is validated by dbt Cloud CI on the PR, which rebuilds
all `state:modified+` marts as tables.)

- [ ] **Step 7: Lint and commit**

```bash
.trunk/tools/trunk check --force src/dbt/kipptaf/dbt_project.yml \
  $(grep -rl 'warn_unenforced: false' src/dbt/kipptaf/models/marts/) 2>&1 | tail -5
git add src/dbt/kipptaf/dbt_project.yml src/dbt/kipptaf/models/marts/
git commit -m "fix(cube): materialize marts as tables to fix cold query latency

Flip marts default view -> table so Cube reads static tables; sweep
warn_unenforced on table-mart constraints. Fixes #4333."
```

(If `dim_staff_reporting_chain` was overridden to view, its yml is included.)

---

## Task 4: Conditional assessment pre-aggregation + measure C

Ship only if the C-vs-B cost/benefit (spec "Performance measurement") justifies
it. Additive-only; never blocks queries.

**Files:**

- Modify (conditional):
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`

**Interfaces:**

- Consumes: Task 1 B numbers; Task 3 tables.
- Produces: either a committed `pre_aggregations` block (if shipped) or a
  recorded defer decision with the C-vs-B numbers.

- [ ] **Step 1: Draft the rollup on the assessment cube**

Add to `student_assessment_scores.yml` (cube level). Dimensions MUST include the
RLS scoping members `region_key` and `abbreviation` (the summary view's
`access_policy` filters on them) or scoped viewers never hit the rollup, plus
the hot-path breakdowns:

```yaml
pre_aggregations:
  - name: proficiency_by_standard_demographic
    measures:
      - count_scores
      - _sum_proficient
    dimensions:
      - student_assessment_administrations.student_assessments.module_code
      - response_type_code
      - student_section_enrollments.student_school_enrollments.students.race
      - student_section_enrollments.student_school_enrollments.students.gender_identity
      - student_section_enrollments.student_school_enrollments.grade_level
      - student_section_enrollments.student_school_enrollments.locations.region_key
      - student_section_enrollments.student_school_enrollments.locations.abbreviation
    time_dimension: student_assessment_administrations.dates.academic_year
    granularity: year
    partition_granularity: year
    refresh_key:
      every: 1 day
```

(Confirm each dotted member path against the summary view's `join_path` blocks
before building — the exact paths are listed in
`student_assessment_scores_summary.yml`. Adjust the demographic set to the
measured hot-path queries.)

- [ ] **Step 2: Rebuild the dev scaffold and pre-build the rollup**

Re-apply the Task 1 Step 2 scaffold, restart the Cube dev server (ask the user),
and issue one query matching the rollup so Cube builds it. Record the **rollup
build time separately** — it is not query latency.

- [ ] **Step 3: Confirm the query HITS the rollup**

Run the repro and inspect the compiled SQL (dev-server logs, or the Cube `/sql`
endpoint). Expected: the `FROM` clause reads a
`dev_pre_aggregations.*proficiency_by_standard_demographic*` table, NOT
`fct_assessment_scores_enrollment_scoped`. If it still reads the fact, the query
does not match the rollup (a grouping/filter dimension is missing from it) —
adjust dimensions and rebuild. **A C number measured on a non-hit is invalid.**

- [ ] **Step 4: Measure C cold and capture BQ stats**

Re-run `.claude/scratch/measure_cube_sql.py` (cold), record median +
rollup-table BQ `total_bytes_processed` / `total_slot_ms`. Fill the A/B/C table.

- [ ] **Step 5: Decide ship vs defer**

Weigh the spec's cost/benefit: C-vs-B latency delta, per-query scan reduction ×
hot-path frequency, growth headroom — against refresh cost + maintenance-drift
risk. Record the decision and numbers.

- [ ] **Step 6a (if shipping): revert scaffold, lint, commit**

```bash
grep -r "zz_" src/cube/ && echo "STILL REDIRECTED" || echo "clean"
.trunk/tools/trunk check --force \
  src/cube/model/cubes/student_assessments/student_assessment_scores.yml 2>&1 | tail -5
git add src/cube/model/cubes/student_assessments/student_assessment_scores.yml
git commit -m "feat(cube): pre-aggregate assessment proficiency hot path

Rollup on additive count_scores/_sum_proficient incl. region_key +
abbreviation so scoped viewers hit it. Refs #4333."
```

- [ ] **Step 6b (if deferring): revert the rollup draft, file a follow-up note**

Revert `student_assessment_scores.yml`, confirm `grep -r zz_ src/cube` clean,
and record the defer rationale + numbers in the PR description for the reviewer.

---

## Task 5: Dagster absorption, RLS regression, docs, PR

**Files:**

- Possibly modify: `src/cube/CLAUDE.md`,
  `src/dbt/kipptaf/models/marts/CLAUDE.md`
- Create (uncommitted): PR body in `.claude/scratch/`

**Interfaces:**

- Consumes: Tasks 3-4.
- Produces: a PR against `main` (base retargets after #4269 merges), with the
  A/B/C table, the RLS-regression evidence, and the post-merge drop note.

- [ ] **Step 1: RLS viewer-matrix regression over the SQL API**

With the dev scaffold up, run the repro as a network viewer, a region viewer, a
school viewer, and a `none`-scope viewer (change the SQL `user` per connection).
Expected: network sees all rows; region sees its region; school sees its school;
`none` sees zero. Materialization must NOT change access behavior. Record
row-count deltas (aggregate counts only — no PII) in the PR draft.

- [ ] **Step 2: Confirm Dagster automation-condition absorption**

Table marts now rematerialize on the data-change automation condition (views did
not). Confirm the wiring exists and the added load is acceptable:

```text
mcp__dagster__list_sensors  -> find kipptaf __automation_condition_sensor
mcp__dagster__get_asset_condition_evaluations for fct_assessment_scores_enrollment_scoped
```

Note in the PR that 75 marts move view (never rebuilt) -> table (rebuilt on
upstream data change), and that the first prod build is a view->table
conversion.

- [ ] **Step 3: Document the post-merge view->table drop**

`create or replace table` does NOT drop a pre-existing view at the same path. In
the PR body, add a release step for the user (prod runs are user-run):

```text
Post-merge, run once (hand to user):
uv run dbt build --select <changed marts> --full-refresh --target prod
(or DROP VIEW the converted relations) so the view->table conversion lands.
```

- [ ] **Step 4: Update CLAUDE.md if a convention shifted**

If marts are now table-by-default, update
`src/dbt/kipptaf/models/marts/CLAUDE.md` / `src/dbt/kipptaf/CLAUDE.md`
inherited- defaults table (view -> table for marts) and note the
`warn_unenforced` sweep as standard. Keep edits minimal per the CLAUDE.md
necessity test.

- [ ] **Step 5: Lint docs, open the PR**

```bash
.trunk/tools/trunk check --force <changed .md files> 2>&1 | tail -5
```

Open the PR with `mcp__github__create_pull_request` using
`.github/pull_request_template.md`, base
`cristinabaldor/feat/claude-cube-security-redesign` (retarget to `main` after
#4269 merges), body from the `.claude/scratch/` draft including the A/B/C table,
RLS matrix, and the post-merge drop step. Reference `Fixes #4333`.

---

## Self-review notes

- **Spec coverage:** layer 1 (flip) → Task 3; layer 2 (full-refresh, no
  incremental) → Task 3 (no incremental config added); layer 3 (pre-agg) → Task
  4; A/B/C measurement → Tasks 1 + 4; WITH RECURSIVE wrinkle → Task 3 Step 5;
  warn_unenforced sweep → Task 3 Steps 2-4; view→table drop → Task 5 Step 3;
  Dagster absorption → Task 5 Step 2; RLS unchanged → Task 5 Step 1.
- **No incremental** anywhere (spec decision) — confirmed absent from all tasks.
- **Member names** (`academic_year`, `module_code`, `count_scores`,
  `_sum_proficient`, `region_key`, `abbreviation`, `race`, `gender_identity`,
  `grade_level`, `response_type_code`) are taken verbatim from
  `student_assessment_scores_summary.yml` and `student_assessment_scores.yml`.
