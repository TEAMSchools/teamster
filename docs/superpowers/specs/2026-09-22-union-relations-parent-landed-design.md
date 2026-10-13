# union_relations views rebuild after a parent's code change lands

Issue: [#4290](https://github.com/TEAMSchools/teamster/issues/4290)

## Problem

A kipptaf `union_relations` wrapper view resolves its column list when it is
built. When an upstream district model changes its columns, the wrapper must
rebuild after the district table carries the new schema, or every reader fails
at BigQuery view expansion.

Today the wrapper triggers on ancestor `code_version_changed`. That operand is
true for exactly one tick: it compares the asset's current code version to the
previous tick's cursor, then overwrites the cursor. So the trigger arms at
deploy, before the district rebuild, and the wrapper either:

- rebuilds against the old district table and consumes the trigger (finalsite
  2026-07-01, amplify PM 2026-09-22), or
- has the armed trigger consumed by a stale run already in flight, while
  `~any_deps_in_progress` holds the correct re-run back (overgrad 2026-07-29).

In all three incidents the district table later rebuilt with the new schema and
nothing re-fired the wrapper.

## Goal

A `union_relations` view behaves like a view, with one extra trigger: it
rebuilds when a parent table's post-code-change rebuild lands. "Code change"
covers the parent's own code or any of its ancestors' code. A plain data refresh
of a parent never triggers it.

Success: all three incidents, replayed as tests, end with the wrapper requested
on the tick after the district table lands, and never on the deploy tick alone.

## Constraints

- The automation condition sensors run in the daemon (`use_user_code_server` is
  unset). Only built-in `AutomationCondition` operands and operators work there.
  A custom condition class would need a separate user-code sensor, capped at 500
  entities.
- Ancestor `code_version_changed` is visible across code-location boundaries
  (confirmed by the 2026-09-22 evaluation records).
- `newly_true()` with no stored cursor treats the whole child true subset as
  newly true. Any trigger built on it must not fire for every wrapper on the
  first evaluation after this change ships.

## Design

All changes are in `src/teamster/core/automation_conditions.py`.

### New builder: `_build_parent_code_change_landed`

For each parent X of the wrapper:

```python
pending = (
    AutomationCondition.code_version_changed()
    | _build_any_ancestor_code_version_changed(max_depth - 1)
).since(AutomationCondition.newly_updated())

landed = AutomationCondition.newly_updated() & (~pending).newly_true()
```

- `pending` is true from the tick X or one of its ancestors changes code until X
  next materializes.
- `landed` is true on the tick `pending` turns off, which is the tick X's
  rebuild lands. The `newly_updated()` conjunct stops the first-evaluation
  `newly_true()` from firing for parents that did not update.

The wrapper looks at its direct parents and recurses through view parents only,
so a table behind a view counts:

```python
condition = AutomationCondition.any_deps_match(landed)
for _ in range(max_depth - 1):
    condition = AutomationCondition.any_deps_match(landed) | (
        AutomationCondition.any_deps_match(condition).allow(view_selection)
    )
```

This mirrors the view-restricted recursion in `_build_any_ancestor_updated`.

### `_build_dbt_condition` change

Add a keyword argument for triggers that reset only on `newly_requested()`:

```python
requested_reset_triggers.since(AutomationCondition.newly_requested())
```

OR-ed alongside the existing `triggers.since(_SINCE_LAST_HANDLED)` and
`code_version_changed().since(newly_updated())` branches. Existing callers pass
nothing and are unchanged.

A wrapper materialization from a stale in-flight run, or from a manual UI run,
does not clear this trigger. The `~in_progress` gate holds the request until the
in-flight run finishes. Cost: at most one redundant view rebuild after a manual
run.

### `dbt_union_relations_automation_condition`

```python
return _build_dbt_condition(
    requested_reset_triggers=_build_parent_code_change_landed(
        view_selection=_VIEW_SELECTION
    ),
)
```

The deploy-tick `_build_any_ancestor_code_version_changed()` trigger is removed.
The wrapper keeps `newly_missing` and its own `code_version_changed`. The
`~any_deps_missing`, `~any_deps_in_progress`, and `~in_progress` gates are
unchanged. Update the docstring to describe the new trigger and the known limits
below.

### Published docs

Update the union_relations section of `docs/reference/automation-conditions.md`
to describe the new trigger. The page is in the `mkdocs.yml` nav.

## Incident walk-through

| Incident   | Parent that lands                                      | Why the wrapper fires                                                                                                                              |
| ---------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| finalsite  | Miami `int_finalsite__enrollment_lifecycle`            | Own code change arms `pending`; the 17:23 rebuild clears it.                                                                                       |
| overgrad   | district `int_overgrad__admissions`                    | `custom_fields_pivot` change arms `pending` on admissions; the 17:46 rebuild clears it. The 17:43 stale run cannot reset a requested-only trigger. |
| amplify PM | Newark `stg_amplify__mclass__sftp__pm_student_summary` | Own code change arms `pending`; the 18:34 rebuild clears it.                                                                                       |

## Testing

In `tests/test_automation_conditions.py`, using `evaluate_automation_conditions`
like the existing tests:

- Rewrite `test_union_relations_view_triggered_by_upstream_code_version_change`
  and `test_union_relations_view_triggered_by_ancestor_code_version_change` to
  assert no request on the deploy tick, then a request on the tick after the
  parent (or the grandparent chain) materializes.
- New: grandparent code change, parent table plain data rebuild, wrapper fires
  once the parent lands (overgrad shape).
- New: wrapper, then a view, then a table with a code change; wrapper fires when
  the table lands.
- New: a wrapper run materializes after the parent lands; the trigger survives
  and the wrapper is requested again.
- New: the first evaluation under the new condition tree, with no parent update,
  requests nothing.
- Keep `test_union_relations_view_not_triggered_by_upstream_data_update`
  unchanged.

Performance: run `tests/test_automation_condition_performance.py` and compare
`warm_elapsed` to the current strategy and `_SENSOR_BUDGET_SECONDS`. If it goes
over budget, lower the inner ancestor depth first.

Prod check after merge: on the next deploy that changes a district package
model, the wrapper's condition evaluations show no request at deploy and a
request on the tick after the district rebuild.

## Known limits

1. A parent that reloads and finishes its rebuild within one kipptaf sensor tick
   is missed: `pending` arms and resets on the same tick, and the reset wins
   because `code_version_changed` carries no timing metadata.
2. If a parent table does a plain data rebuild before its changed ancestor
   rebuilds, `pending` clears early and the wrapper fires against the old
   schema. The later rebuild does not re-fire it.
3. A phantom `pending` (cursor state from a past tick) costs at most one extra
   view rebuild, plus the downstream tables that already rebuild on any parent
   update. It cannot deadlock, because this is a trigger, not a gate.

## Out of scope

- Moving any sensor to `use_user_code_server`.
- Changing view, table, or cron conditions.
- Side finding, unverified: because the daemon evaluates the conditions, the
  `_patched_get_dep_keys` monkey-patch may only take effect in tests. Worth a
  separate issue if confirmed.
