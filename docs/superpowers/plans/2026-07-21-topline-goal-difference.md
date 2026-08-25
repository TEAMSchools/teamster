# Topline difference-from-goal and enrollment numerator/denominator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a direction-aware difference-from-goal (percentage points for
proportion metrics, whole numbers for counts) and expose the raw enrolled count
and target integer behind the enrollment percentages, so Tableau can show both
via the existing header-drop coalesce trick.

**Architecture:** Two additive edits to `int_topline__dashboard_aggregations` (a
new `goal_difference` computed from `goal_resolved`, split into typed siblings
by `aggregation_data_type`; and `metric_numerator` / `metric_denominator`
carried forward on the enrollment-target rows), passed through
`rpt_tableau__topline_cascade_dashboard`. No existing column changes; no Tableau
work in this plan.

**Tech Stack:** dbt (BigQuery), kipptaf project. Spec:
`docs/superpowers/specs/2026-07-21-topline-goal-difference-design.md`. Issue
#4487. Lands on branch `anthonygwalters/feat/claude-topline-multigrain` (PR
#4370).

## Global Constraints

- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/topline-goal-diff`. Every `git` call uses
  `git -C /workspaces/teamster/.worktrees/topline-goal-diff`. Every Read / Edit
  / Write targets the worktree path, never `/workspaces/teamster/<path>`.
- **dbt commands** run with `--project-dir`
  `/workspaces/teamster/.worktrees/topline-goal-diff/src/dbt/kipptaf` and
  `--state /workspaces/teamster/src/dbt/kipptaf/target/prod` (absolute, main
  repo's prod manifest). Never `--target prod` (classifier-blocked); use
  `--target dev --defer`.
- **Dev schema** for verification queries:
  `teamster-332318.zz_anthonygwalters_kipptaf_topline.int_topline__dashboard_aggregations`.
- **SQL guide** (`src/dbt/CLAUDE.md`): max 1 level of function nesting; no
  `QUALIFY` / `ORDER BY` / `GROUP BY ALL` / table subqueries; ST06 column
  ordering (plain refs grouped by source table, then constants, simple
  functions, nested, logicals, case, window); trailing comma on every `SELECT`
  item; 88-char lines; single-quoted strings.
- **Do NOT touch** existing columns or logic: `goal_direction` baseball/golf
  stays exactly as-is; `is_goal_met`, `goal_difference_percent`,
  `progress_to_goal_pct`, `metric_aggregate_value*` are unchanged. The
  `where term <= current_date(...)` filter on the final select stays.
- **Do NOT** add `select distinct`, `qualify row_number()=1`, or
  `dbt_utils.deduplicate` anywhere — no dedup is needed; grain is unchanged.
- **Types:** `goal_difference`, `goal_difference_numeric`,
  `goal_difference_integer` are `float64` (a `float64 - numeric` subtraction is
  `float64`). `metric_numerator`, `metric_denominator` are `numeric`.
- The intermediate model is **not** contract-enforced; its yml still carries
  `data_type` per column for documentation — match that pattern. The `rpt_`
  extract **is** contract-enforced — its yml `data_type` must match the SQL
  output type exactly.

---

## Prep (orchestrator, before dispatching Task 1)

Not a subagent task. Run these once so subagents can build the single changed
model against fresh dev upstreams and compare against a baseline.

- [ ] **P1: Merge main into the branch.**

```bash
cd /workspaces/teamster/.worktrees/topline-goal-diff
git fetch origin main
git merge origin/main
```

Resolve any conflicts (none expected in the topline models). If
`int_topline__dashboard_aggregations.sql` conflicts, keep the branch version and
re-apply main's changes around it.

- [ ] **P2: Materialize the branch-new topline upstream chain into dev.** This
      builds the models that do not exist in prod (periods, period variants,
      seeds, goals staging) so later single-model builds resolve via `--defer`.

```bash
cd /workspaces/teamster/.worktrees/topline-goal-diff
uv run dbt build \
  --select path:models/topline stg_google_sheets__topline_period_goals \
    stg_google_sheets__topline_aggregate_goals stg_google_sheets__topline_enrollment_targets \
    int_google_sheets__topline_aggregate_goals \
    seed_topline_period_rollup seed_topline_period_goals \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/topline-goal-diff/src/dbt/kipptaf
```

Expected: builds succeed; the aggregation PK uniqueness test WARNs (~359 rows,
pre-existing — see PR #4370). If a deferred prod ancestor errors with a missing
column, add it to `--select` and re-run.

- [ ] **P3: Capture the baseline checksum of existing output columns** (used in
      Task 1 and Task 2 to prove nothing else moved). Run via BigQuery MCP:

```sql
select
  period_type,
  count(*) as n,
  bit_xor(farm_fingerprint(format(
    '%T|%T|%T|%T|%T|%T|%T|%T|%T|%T|%T',
    metric_type, academic_year, region, schoolid, layer, indicator,
    term, period_label, goal, metric_aggregate_value, goal_difference_percent
  ))) as chk
from `teamster-332318`.zz_anthonygwalters_kipptaf_topline.int_topline__dashboard_aggregations
group by period_type
order by period_type
```

Record the four `(period_type, n, chk)` rows.

---

### Task 1: `goal_difference` and typed split, plus enrollment numerator/denominator

**Files:**

- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__dashboard_aggregations.sql`
- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__dashboard_aggregations.yml`

**Interfaces:**

- Consumes: `resolved_goals.goal_resolved` (numeric, the resolved goal),
  `metric_aggregate_value` (float64), `has_goal` (bool), `goal_direction`
  (string: `baseball` / `golf` / null), `aggregation_data_type` (string:
  `Numeric` / `Integer`); `target_goals` operands `tu.metric_aggregate_value`
  (enrolled count) and `tu.goal` (target integer).
- Produces: five new output columns on `int_topline__dashboard_aggregations`,
  consumed by Task 3 — `goal_difference` (float64), `goal_difference_numeric`
  (float64), `goal_difference_integer` (float64), `metric_numerator` (numeric),
  `metric_denominator` (numeric).

**Subagent must run first:** `Skill` with
skill=`dbt:using-dbt-for-analytics-engineering`. Read `src/dbt/CLAUDE.md` (SQL
conventions, ST06) and this model in full before editing.

- [ ] **Step 1: Add `metric_numerator` / `metric_denominator` in
      `target_goals`.** In the `target_goals` CTE (the `tu`-column group, before
      the `tg` group), add two aliased, cast operands. Place them among the
      `tu.` refs:

```sql
            cast(tu.metric_aggregate_value as numeric) as metric_numerator,
            cast(tu.goal as numeric) as metric_denominator,
```

(These are the raw enrolled count and the seat/budget target — the operands the
existing `round(safe_divide(tu.metric_aggregate_value, tu.goal), 3)` consumes.)

- [ ] **Step 2: Thread the two columns through both `with_target_rows`
      branches.** In the first branch (`from all_rows`), add null placeholders
      in the same position as the `metric_aggregate_value` line:

```sql
            metric_aggregate_value,
            cast(null as numeric) as metric_numerator,
            cast(null as numeric) as metric_denominator,
```

In the second branch (`from target_goals`), project the real columns in the same
position:

```sql
            metric_aggregate_value,
            metric_numerator,
            metric_denominator,
```

- [ ] **Step 3: Add the `resolved_with_diff` CTE** immediately after the
      `resolved_goals` CTE closes (after its `)` near line 1051), before the
      final `select`. It computes the direction-aware difference where
      `goal_resolved` is a real column:

```sql
    resolved_with_diff as (
        select
            *,

            case
                when not has_goal
                then null
                when goal_direction = 'baseball'
                then metric_aggregate_value - goal_resolved
                when goal_direction = 'golf'
                then goal_resolved - metric_aggregate_value
            end as goal_difference,
        from resolved_goals
    )
```

- [ ] **Step 4: Point the final `select` at the new CTE.** Change the last line
      from `from resolved_goals` to `from resolved_with_diff` (keep the
      following `where term <= current_date('{{ var("local_timezone") }}')`).

- [ ] **Step 5: Project the new columns in the final `select`.** Add
      `goal_difference`, `metric_numerator`, `metric_denominator` to the
      plain-column group (next to `metric_aggregate_value`), and add the typed
      split next to the existing `metric_aggregate_value_numeric` /
      `metric_aggregate_value_integer` block:

```sql
    if(
        aggregation_data_type = 'Numeric', goal_difference, null
    ) as goal_difference_numeric,
    if(
        aggregation_data_type = 'Integer', goal_difference, null
    ) as goal_difference_integer,
```

Keep ST06 order: plain refs (`goal_difference`, `metric_numerator`,
`metric_denominator`) go with the other plain columns above the constants/`if`
block; the two `if(...)` splits go in the simple-function group with the value
splits. `is_goal_met` / `goal_difference_percent` / `progress_to_goal_pct` are
untouched.

- [ ] **Step 6: Document the five columns in the int yml.** In
      `int_topline__dashboard_aggregations.yml`, add entries matching the file's
      `- name: / data_type: / description:` pattern:

```yaml
- name: goal_difference
  data_type: float64
  description:
    Direction-aware difference between the aggregate value and the resolved
    goal, in the metric's own units — positive means ahead of goal. baseball
    (higher is better) is value minus goal; golf (lower is better) is goal minus
    value. Null when the row has no goal or no direction.
- name: goal_difference_numeric
  data_type: float64
  description:
    goal_difference for proportion (Numeric) indicators, else null — a
    proportion delta Tableau formats as percentage points. Mirrors the
    metric_aggregate_value_numeric routing.
- name: goal_difference_integer
  data_type: float64
  description:
    goal_difference for count (Integer) indicators, else null — a whole-number
    difference. Mirrors the metric_aggregate_value_integer routing.
- name: metric_numerator
  data_type: numeric
  description:
    Raw numerator behind a ratio row — the enrolled count on Seat Target /
    Budget Target rows; null for every other indicator.
- name: metric_denominator
  data_type: numeric
  description:
    Raw denominator behind a ratio row — the seat or budget target integer on
    Seat Target / Budget Target rows; null for every other indicator.
```

- [ ] **Step 7: Build the model in dev.**

```bash
cd /workspaces/teamster/.worktrees/topline-goal-diff
uv run dbt build --select int_topline__dashboard_aggregations \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/topline-goal-diff/src/dbt/kipptaf 2>&1 | tail -15
```

Expected: `PASS` on the build; the PK uniqueness test WARNs at the same
pre-existing count as Prep (not ERROR). No new failures.

- [ ] **Step 8: Verify `goal_difference` sign and routing** via BigQuery MCP.
      Every row must populate exactly one of the two typed columns, matching its
      `aggregation_data_type`, and the sign must follow direction:

```sql
select
  countif(goal_difference_numeric is not null and aggregation_data_type != 'Numeric') as num_misrouted,
  countif(goal_difference_integer is not null and aggregation_data_type != 'Integer') as int_misrouted,
  countif(has_goal and goal_direction = 'baseball'
          and round(goal_difference, 6) != round(metric_aggregate_value - cast(goal as float64), 6)) as baseball_wrong,
  countif(has_goal and goal_direction = 'golf'
          and round(goal_difference, 6) != round(cast(goal as float64) - metric_aggregate_value, 6)) as golf_wrong,
  countif(not has_goal and goal_difference is not null) as nogoal_notnull
from `teamster-332318`.zz_anthonygwalters_kipptaf_topline.int_topline__dashboard_aggregations
```

Expected: all five counts `0`.

- [ ] **Step 9: Verify enrollment operands.** Populated only on target rows, and
      they reproduce the displayed ratio:

```sql
select
  countif(metric_numerator is not null
          and indicator not in ('Seat Target', 'Budget Target')) as num_offtarget,
  countif(indicator in ('Seat Target', 'Budget Target') and metric_numerator is null) as target_missing_num,
  countif(indicator in ('Seat Target', 'Budget Target')
          and round(safe_divide(metric_numerator, metric_denominator), 3) != round(metric_aggregate_value, 3)) as ratio_mismatch
from `teamster-332318`.zz_anthonygwalters_kipptaf_topline.int_topline__dashboard_aggregations
```

Expected: `num_offtarget = 0`, `ratio_mismatch = 0`. (`target_missing_num` may
be nonzero only if a target row has a null enrolled count upstream — investigate
if so, but it does not block.)

- [ ] **Step 10: Regression — existing columns unchanged.** Re-run the Prep P3
      checksum query. The four `(period_type, n, chk)` rows must match the Prep
      baseline exactly (the new columns are excluded from that checksum, so any
      change means an existing column moved — investigate before proceeding).

- [ ] **Step 11: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/topline-goal-diff add \
  src/dbt/kipptaf/models/topline/intermediate/int_topline__dashboard_aggregations.sql \
  src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__dashboard_aggregations.yml
git -C /workspaces/teamster/.worktrees/topline-goal-diff commit -m "feat(kipptaf): add topline goal_difference and enrollment num/denom

Refs #4487"
```

---

### Task 2: Extract pass-through and contract

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__topline_cascade_dashboard.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__topline_cascade_dashboard.yml`

**Interfaces:**

- Consumes: the five columns Task 1 produced on
  `int_topline__dashboard_aggregations`.
- Produces: the same five columns on the contract-enforced extract, for Tableau.

**Subagent must run first:** `Skill` with
skill=`dbt:using-dbt-for-analytics-engineering`. Read the `rpt_` model and its
yml in full first.

- [ ] **Step 1: Pass the columns through the `rpt_` select.** After the existing
      `db.progress_to_goal_pct,` line, add:

```sql
    db.goal_difference,
    db.goal_difference_numeric,
    db.goal_difference_integer,
    db.metric_numerator,
    db.metric_denominator,
```

(These are plain `db.` refs; keep them in the `db` column group.)

- [ ] **Step 2: Declare the five columns in the contract yml.** In
      `rpt_tableau__topline_cascade_dashboard.yml`, add after the
      `progress_to_goal_pct` entry (contract matches by name+type, so position
      is free):

```yaml
- name: goal_difference
  data_type: float64
  description:
    Direction-aware difference from the resolved goal (positive means ahead of
    goal), in the metric's own units.
- name: goal_difference_numeric
  data_type: float64
  description:
    goal_difference for proportion indicators, else null — formats as percentage
    points in Tableau.
- name: goal_difference_integer
  data_type: float64
  description: goal_difference for count indicators, else null.
- name: metric_numerator
  data_type: numeric
  description:
    Enrolled count behind the Seat Target / Budget Target ratio; null for other
    indicators.
- name: metric_denominator
  data_type: numeric
  description:
    Seat or budget target integer behind the ratio; null for other indicators.
```

- [ ] **Step 3: Build the extract in dev.**

```bash
cd /workspaces/teamster/.worktrees/topline-goal-diff
uv run dbt build --select rpt_tableau__topline_cascade_dashboard \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/topline-goal-diff/src/dbt/kipptaf 2>&1 | tail -15
```

Expected: build PASS (contract satisfied — a type mismatch would ERROR here),
uniqueness test at its pre-existing state.

- [ ] **Step 4: Verify parity with the intermediate.** The extract exposes the
      five columns and preserves them row-for-row:

```sql
select
  count(*) as n_rows,
  countif(goal_difference_numeric is not null) as n_num,
  countif(goal_difference_integer is not null) as n_int,
  countif(metric_numerator is not null) as n_enroll
from `teamster-332318`.zz_anthonygwalters_kipptaf_tableau.rpt_tableau__topline_cascade_dashboard
```

Expected: nonzero `n_num`, `n_int`, `n_enroll`; `n_rows` matches the extract's
pre-change row count (the extract adds columns only, not rows).

- [ ] **Step 5: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/topline-goal-diff add \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__topline_cascade_dashboard.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__topline_cascade_dashboard.yml
git -C /workspaces/teamster/.worktrees/topline-goal-diff commit -m "feat(kipptaf): expose topline goal_difference and enrollment num/denom in extract

Refs #4487"
```

---

### Task 3: Whole-branch reconciliation and lint gate

Not a code task — a verification gate before pushing. No commit unless a fix is
needed (then re-run the affected task).

- [ ] **Step 1: Full downstream build of the two models and their tests.**

```bash
cd /workspaces/teamster/.worktrees/topline-goal-diff
uv run dbt build --select int_topline__dashboard_aggregations rpt_tableau__topline_cascade_dashboard \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/topline-goal-diff/src/dbt/kipptaf 2>&1 | tail -15
```

Expected: PASS; only the pre-existing PK WARN.

- [ ] **Step 2: Lint the changed files.** From inside the worktree, using the
      main repo's trunk binary:

```bash
cd /workspaces/teamster/.worktrees/topline-goal-diff
CI=1 /workspaces/teamster/.trunk/tools/trunk check --force --no-fix </dev/null \
  src/dbt/kipptaf/models/topline/intermediate/int_topline__dashboard_aggregations.sql \
  src/dbt/kipptaf/models/topline/intermediate/properties/int_topline__dashboard_aggregations.yml \
  src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__topline_cascade_dashboard.sql \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__topline_cascade_dashboard.yml 2>&1 | tail -15
```

Expected: `No issues` (sqlfluff / yamllint clean). Fix any finding in the owning
task and re-commit.

- [ ] **Step 3: Spot-check a few real rows** across a baseball proportion, a
      golf proportion, an integer count, and an enrollment target row,
      confirming the displayed sign and units read correctly:

```sql
select indicator, aggregation_display, period_type, period_label,
  round(metric_aggregate_value, 3) as value, goal,
  round(goal_difference, 3) as goal_difference,
  metric_numerator, metric_denominator
from `teamster-332318`.zz_anthonygwalters_kipptaf_topline.int_topline__dashboard_aggregations
where has_goal and is_current_period
  and indicator in ('ADA', 'Chronic Absenteeism', 'Total Enrollment', 'Seat Target')
order by indicator, period_type
limit 20
```

Confirm: baseball rows behind goal show negative; golf rows over the cap show
negative; Seat Target rows carry numerator/denominator.

- [ ] **Step 4: Push to PR #4370** (orchestrator; confirm dbt Cloud CI is in a
      terminal state first so the push does not cancel a running check):

```bash
git -C /workspaces/teamster/.worktrees/topline-goal-diff push origin HEAD
```

Then watch dbt Cloud CI; after it passes, fetch warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` and confirm
the only warning is the pre-existing aggregation PK.

---

## Self-Review

**Spec coverage:**

- Feedback #1 (typed difference from goal, direction-aware, ahead=positive) →
  Task 1 Steps 3-5, 8. ✓
- Feedback #2 (enrollment numerator/denominator, enrollment-only) → Task 1 Steps
  1-2, 9. ✓
- Extract pass-through + contract types → Task 2. ✓
- Color banding unchanged / existing columns unchanged → Task 1 Step 10
  regression check; Global Constraints. ✓
- Known pre-existing warts (SCD, i-Ready Time on Task) → out of scope by design;
  no task, correctly (data-team owned). ✓
- Tableau presentation → out of scope for this plan (spec §4 is a Tableau-side
  note). ✓

**Placeholder scan:** none — every step has exact code or an exact command with
expected output.

**Type consistency:** `goal_difference` / `_numeric` / `_integer` are `float64`
in both the int yml (Task 1 Step 6) and the rpt contract (Task 2 Step 2);
`metric_numerator` / `metric_denominator` are `numeric` in both. Column names
are identical across Task 1 (produced), Task 2 (consumed), and the verification
queries.
