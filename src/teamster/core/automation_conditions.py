from dagster import AssetSelection, AutomationCondition
from dagster._core.definitions.declarative_automation.operators.dep_operators import (
    DepsAutomationCondition,
)

_MAX_VIEW_DEPTH = 5


def _external_source_selection() -> AssetSelection:
    return AssetSelection.all(include_sources=True) - AssetSelection.all(
        include_sources=False
    )


def _build_any_ancestor_updated(
    max_depth: int = _MAX_VIEW_DEPTH,
) -> DepsAutomationCondition:
    """Detect updates in ancestor assets up to `max_depth` levels of indirection.

    For a chain like Table_A -> View_1 -> ... -> View_N -> Table_B,
    this condition on Table_B detects when Table_A is updated, even though
    the intermediate views were not re-materialized.

    Works by recursively nesting any_deps_match to look through each level.
    """
    condition = AutomationCondition.any_deps_updated()

    for _ in range(max_depth):
        condition = (
            AutomationCondition.any_deps_updated()
            | AutomationCondition.any_deps_match(condition)
        )

    return AutomationCondition.any_deps_match(condition)


def dbt_view_automation_condition(
    ignore_selection: AssetSelection,
) -> AutomationCondition:
    """Automation condition for dbt VIEW models.

    Views are computed on read and don't store physical data, so they only
    need re-materialization when:
    - Initially missing (newly_missing)
    - SQL code changes (code_version_changed)
    """
    return (
        AutomationCondition.in_latest_time_window()
        & (
            AutomationCondition.newly_missing()
            | AutomationCondition.code_version_changed()
        ).since(
            AutomationCondition.newly_requested() | AutomationCondition.newly_updated()
        )
        & ~AutomationCondition.any_deps_missing().ignore(
            ignore_selection | _external_source_selection()
        )
        & ~AutomationCondition.any_deps_in_progress().ignore(ignore_selection)
        & ~AutomationCondition.in_progress()
    )


def dbt_table_automation_condition(
    ignore_selection: AssetSelection,
) -> AutomationCondition:
    """Automation condition for dbt TABLE models.

    Tables store physical data and must be re-materialized when upstream
    data changes. Uses nested any_deps_match to detect upstream table
    updates through intermediate views that aren't re-materialized.
    """
    return (
        AutomationCondition.in_latest_time_window()
        & (
            AutomationCondition.newly_missing()
            | AutomationCondition.any_deps_updated().ignore(ignore_selection)
            | _build_any_ancestor_updated().ignore(ignore_selection)
            | AutomationCondition.code_version_changed()
        ).since(
            AutomationCondition.newly_requested() | AutomationCondition.newly_updated()
        )
        & ~AutomationCondition.any_deps_missing().ignore(
            ignore_selection | _external_source_selection()
        )
        & ~AutomationCondition.any_deps_in_progress().ignore(ignore_selection)
        & ~AutomationCondition.in_progress()
    )
