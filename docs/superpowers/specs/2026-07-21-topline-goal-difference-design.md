# Topline: difference-from-goal and enrollment numerator/denominator

Issue: [#4487](https://github.com/TEAMSchools/teamster/issues/4487). Builds on
the multigrain refactor in
[#4370](https://github.com/TEAMSchools/teamster/pull/4370) and lands on that
branch (`anthonygwalters/feat/claude-topline-multigrain`) — it references
`goal_resolved` and the unified final `SELECT` that PR introduces.

## Motivation

Two stakeholder requests the current dashboard cannot answer, both rooted in the
same limitation: the model reduces each metric to a single ratio and discards
the raw operands.

1. **Difference from goal, at every level.** Stakeholders want a
   percentage-point difference from goal for proportion metrics, and a
   whole-number difference for integer metrics. Today the only goal comparison
   in the extract is `goal_difference_percent` — a _relative_ percent
   (`(goal - value) / goal`) that drives the Big Board color banding. The
   absolute difference they want is not present, even though both operands
   (`metric_aggregate_value` and `goal_resolved`) sit on every row.

2. **Enrollment target detail.** On the enrollment layer, a school shows as "97%
   enrolled". Stakeholders want the tooltip to show what that represents — the
   real enrolled count against the integer target (e.g. "1,047 of 1,080"). Both
   raw numbers are discarded: the ratio is computed as
   `safe_divide(enrolled, target)` and neither the enrolled count nor the target
   integer survives.

## Background — how the model already handles data types

Two independent per-indicator controls come from the aggregate goals sheet:

- `aggregation_type` governs math and rounding: `Average` and `Divide` round to
  three decimals, `Sum` rounds to zero
  (`int_topline__dashboard_aggregations.sql`).
- `aggregation_data_type` (`Numeric` / `Integer`) governs output routing. The
  final `SELECT` fans the single `metric_aggregate_value` into
  `metric_aggregate_value_numeric` (populated when `Numeric`, else null) and
  `metric_aggregate_value_integer` (when `Integer`, else null). Tableau binds
  each worksheet to the column whose number format it wants and coalesces them
  into one visual column by dropping the unused measure's headers.

Every `Numeric` indicator in the current data is a 0-1 proportion (rates,
percentages, and even "Weighted Y1 GPA", which is stored as the share of
students meeting the GPA bar). Every `Integer` indicator is a count. So the
proportion-versus-integer split the stakeholders describe already exists as
`aggregation_data_type`.

At the warehouse level this is _routing plus rounding_, not true typing: all
three value columns are `float64` in the contract; `goal` is `numeric`.

## Design

Principle: **dbt carries the raw building blocks; Tableau formats and drops
headers** — the same division of labor that already works for the value column.

### 1. Difference from goal (`goal_difference` and its typed split)

Compute one direction-aware difference where `goal_resolved` is finalized (the
`resolved_goals` CTE), then split it in the final `SELECT` exactly parallel to
the value columns.

Sign convention: **ahead of goal is positive** (direction-aware).

```sql
-- resolved_goals: raw difference in the metric's own units
case
    when not has_goal then null
    when goal_direction = 'baseball' then metric_aggregate_value - goal_resolved
    when goal_direction = 'golf' then goal_resolved - metric_aggregate_value
end as goal_difference,
```

```sql
-- final SELECT: routed by aggregation_data_type, mirroring the value columns
if(aggregation_data_type = 'Numeric', goal_difference, null) as goal_difference_numeric,
if(aggregation_data_type = 'Integer', goal_difference, null) as goal_difference_integer,
```

Behavior:

- Baseball (higher is better): `value - goal`. ADA 0.92 vs 0.95 goal → `-0.03`.
- Golf (lower is better): `goal - value`. Chronic Absenteeism 0.12 vs 0.10 goal
  → `-0.02` (behind, because 12 percent is worse than the 10 percent cap).
- Enrollment (baseball, count): 1,047 vs 1,080 → `-33` (33 behind).
- `has_goal = false` or `goal_direction` null (FAST, State Assessments, one
  Truancy row) → null, consistent with the existing `is_goal_met` /
  `goal_difference_percent` being null there.

`goal_difference_numeric` is a proportion delta (e.g. `-0.03`) that Tableau
percent-formats to "-3.0%", read as 3 percentage points — the same way
`metric_aggregate_value_numeric = 0.92` renders "92.0%".

The existing `goal_difference_percent` and `progress_to_goal_pct` are unchanged;
the absolute difference is additive.

### 2. Enrollment numerator and denominator

In the `target_goals` CTE — where the ratio is formed and both operands are
currently dropped — carry them forward:

```sql
tu.metric_aggregate_value as metric_numerator,   -- enrolled count (1,047)
tu.goal as metric_denominator,                    -- seat/budget target (1,080)
```

Populated only on the Seat Target / Budget Target rows; null for every other
indicator. **Enrollment-only by decision (YAGNI)** — other ratio metrics (ADA,
Successful Contacts) are not carried, though the same pattern would extend to
them later if asked.

Because the model unions many branches into `all_rows` before the final
`SELECT`, these two columns must reach the output either by (a) projecting them
(null) in every union branch, or (b) attaching them via a final left join keyed
on the target rows' identity. The implementation plan will choose the
least-invasive threading; both are pure plumbing with no semantic difference.

### 3. Extract and contract

`rpt_tableau__topline_cascade_dashboard` passes the new columns through, and its
properties YAML declares them:

- `goal_difference`, `goal_difference_numeric`, `goal_difference_integer` —
  `float64` (matching the value columns and `goal_difference_percent`).
- `metric_numerator`, `metric_denominator` — `numeric` (whole-number counts;
  matches `goal`).

All new columns get descriptions; no existing column is renamed or removed, so
the contract change is additive.

### 4. Tableau presentation

- **Difference from goal:** `goal_difference_numeric` and
  `goal_difference_integer` become two measures coalesced by dropping the unused
  measure's headers — identical to the value trick. Default placement is the
  tooltip; optionally a parameter can swap the cell measure between value and
  difference. This is a Tableau-side choice, iterable without model changes.
- **Enrollment:** the Seat/Budget Target tooltip shows `metric_numerator` "of"
  `metric_denominator` (with the existing percent), e.g. "1,047 of 1,080 (97%)".
- **Color banding is unchanged** — it stays on the relative
  `goal_difference_percent` / `progress_to_goal_pct`.

## Known pre-existing issues (out of scope; data-team owned)

Neither is introduced by this work; both surface through it because the
difference reuses `aggregation_data_type`. The difference has no independent
typing failure mode — it can only inherit whatever the value already does. Fixes
are owned by the data team and tracked separately.

- **School Community Diagnostic** is tagged `aggregation_data_type = Integer`
  but is a 1-4 scale average (values 2.7-3.1, network average 2.907, goal 3).
  Both its value and its difference route to the integer lane and round to whole
  numbers, so a `+0.137` difference reads as "0". A one-cell goals-sheet change
  (tag to `Numeric`) corrects value and difference together.
- **i-Ready Time on Task** carries values on a minutes scale (0-140, average
  38.9) against a proportion goal (0.8). Its difference is as meaningless as its
  current value and color banding. Needs an upstream metric-definition
  reconciliation. (A second grouping of rows matches no goal at all — a separate
  coverage gap.)

## Verification

- Full downstream build of `int_topline__dashboard_aggregations`,
  `rpt_tableau__topline_cascade_dashboard`, and their tests in dev.
- `goal_difference` reconciliation: for a sample across baseball, golf, and the
  enrollment-target rows, confirm the sign and magnitude match hand calculation
  and that exactly one of `goal_difference_numeric` / `goal_difference_integer`
  is populated per row (the other null), matching the row's
  `aggregation_data_type`.
- `metric_numerator` / `metric_denominator` populated only on Seat/Budget Target
  rows, null elsewhere; `safe_divide(metric_numerator, metric_denominator)`
  reproduces the displayed ratio.
- No change to existing columns: `metric_aggregate_value*`,
  `goal_difference_percent`, `progress_to_goal_pct`, and `is_goal_met` unchanged
  versus the pre-change branch build.

## Rollout

Commits land on the `anthonygwalters/feat/claude-topline-multigrain` branch and
ship as part of PR #4370. `main` is merged into the branch before the code
changes so CI builds against current upstream. No external-source or seed
changes; CI stays self-contained.
