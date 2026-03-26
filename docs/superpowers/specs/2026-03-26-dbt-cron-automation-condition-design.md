# dbt Cron Automation Condition — Design Spec

**Date:** 2026-03-26 **Status:** Draft

## Problem

dbt data tests inherit `dbt_table_automation_condition()`, which triggers on
every upstream materialization. For tests that flag known data quality issues
that can't be resolved immediately (e.g., GPA anomalies), this creates noise —
the same warnings fire on every run with no new information.

There is no mechanism to schedule a dbt test (or model) on a cron cadence
instead of the default dependency-based trigger.

## Goals

- Allow any dbt node (test or model) to opt into cron-based scheduling via
  `meta.dagster.cron_schedule` in the dbt config block
- Retain all existing safety guards from `_build_dbt_condition()` (missing deps,
  in-progress checks, latest time window)
- Zero config changes needed in Dagster Python code to schedule a new node —
  just add the meta key in dbt SQL/YAML

## Out of Scope

- Changes to `dbt build` execution logic or test selection
- Separate Dagster jobs or schedules for tests
- Changes to existing automation conditions for views, tables, or union
  relations

## Architecture

### New automation condition builder

`src/teamster/core/automation_conditions.py`:

```python
def dbt_cron_automation_condition(cron_schedule: str) -> AutomationCondition:
    """Automation condition for dbt assets on a cron schedule.

    Triggers on cron ticks instead of upstream data changes. Retains all
    shared safety guards (missing deps, in-progress, latest time window).
    """
    return _build_dbt_condition(
        AutomationCondition.cron_tick_passed(cron_schedule=cron_schedule)
    )
```

This slots `cron_tick_passed` into the same position where
`any_ancestor_updated` goes for tables — the `_build_dbt_condition()` skeleton
handles everything else.

### Translator dispatch

`src/teamster/libraries/dbt/dagster_dbt_translator.py` —
`get_automation_condition()` gains a priority check at the top:

```python
def get_automation_condition(
    self, dbt_resource_props: Mapping[str, Any]
) -> AutomationCondition | None:
    dbt_meta = dbt_resource_props.get("config", {}).get(
        "meta", {}
    ) or dbt_resource_props.get("meta", {})
    cron_schedule = dbt_meta.get("dagster", {}).get("cron_schedule")

    if cron_schedule is not None:
        return dbt_cron_automation_condition(cron_schedule)

    # existing materialization-type dispatch unchanged
    materialized = dbt_resource_props.get("config", {}).get(
        "materialized", "view"
    )
    ...
```

The `dbt_meta` extraction mirrors the existing pattern in `get_asset_key()`
(lines 30-32). The cron check runs first, so it works regardless of
materialization type.

### dbt config usage

Any dbt node can opt in by adding `cron_schedule` to `meta.dagster`:

```python
{{
    config(
        severity="warn",
        store_failures=true,
        store_failures_as="view",
        meta={
            "dagster": {
                "ref": {"name": "int_powerschool__gpa_cumulative"},
                "cron_schedule": "0 0 * * 0",
            },
        },
    )
}}
```

Standard cron expressions — `"0 0 * * 0"` is weekly Sunday midnight UTC.

## Files Changed

| File                                                         | Change                                                                   |
| ------------------------------------------------------------ | ------------------------------------------------------------------------ |
| `src/teamster/core/automation_conditions.py`                 | Add `dbt_cron_automation_condition()` (~8 lines)                         |
| `src/teamster/libraries/dbt/dagster_dbt_translator.py`       | Add cron check in `get_automation_condition()` (~7 lines), update import |
| `src/dbt/kipptaf/tests/test_gpa_cumulative_data_quality.sql` | Add `"cron_schedule": "0 0 * * 0"` to meta                               |

## Verification

1. `uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions`
   — confirms the automation condition parses and the asset graph loads
2. Dagster UI — verify the test asset shows cron-based triggering instead of
   dependency-based under its automation condition
3. Confirm other tests/models without `cron_schedule` are unaffected

## Availability

This feature is available to all code locations (kipptaf, kippnewark,
kippcamden, kippmiami, kipppaterson) since the changes are in shared library
code. Any dbt node in any project can use `meta.dagster.cron_schedule`.
