from typing import AbstractSet

from dagster import AssetSelection, AutomationCondition
from dagster._core.definitions.asset_key import AssetKey
from dagster._core.definitions.assets.graph.base_asset_graph import (
    BaseAssetGraph,
    BaseAssetNode,
)
from dagster._core.definitions.declarative_automation.operators.dep_operators import (
    DepsAutomationCondition,
)

_MAX_VIEW_DEPTH = 5
_VIEW_SELECTION = AssetSelection.tag("dagster/materialized", "view")


def _patched_get_dep_keys(
    self: DepsAutomationCondition,
    key: AssetKey,
    asset_graph: BaseAssetGraph[BaseAssetNode],
) -> AbstractSet[AssetKey]:
    """Patched _get_dep_keys that copies the set before mutating.

    Fixes a Dagster bug where allow/ignore selections use in-place set
    operations (&=, -=) on the mutable set returned by parent_entity_keys,
    permanently corrupting the asset graph's dependency information.
    """
    dep_keys = set(asset_graph.get(key).parent_entity_keys)
    if self.allow_selection is not None:
        dep_keys &= self.allow_selection.resolve(asset_graph, allow_missing=True)
    if self.ignore_selection is not None:
        dep_keys -= self.ignore_selection.resolve(asset_graph, allow_missing=True)
    return dep_keys


DepsAutomationCondition._get_dep_keys = _patched_get_dep_keys  # type: ignore[assignment]


def _external_source_selection() -> AssetSelection:
    return AssetSelection.all(include_sources=True) - AssetSelection.all(
        include_sources=False
    )


def _build_any_ancestor_updated(
    max_depth: int = _MAX_VIEW_DEPTH,
    view_selection: AssetSelection | None = None,
) -> DepsAutomationCondition:
    """Detect updates in ancestor assets through intermediate views.

    For a chain like Table_A -> View_1 -> ... -> View_N -> Table_B,
    this condition on Table_B detects when Table_A is updated, even though
    the intermediate views were not re-materialized.

    If view_selection is provided, recursion only follows deps matching that
    selection (i.e., views), stopping at the nearest table boundary. This
    avoids exponential blowup when evaluating wide DAGs.
    """
    condition = AutomationCondition.any_deps_updated()

    for _ in range(max_depth):
        recurse = AutomationCondition.any_deps_match(condition)
        if view_selection is not None:
            recurse = recurse.allow(view_selection)
        condition = AutomationCondition.any_deps_updated() | recurse

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
            | _build_any_ancestor_updated(view_selection=_VIEW_SELECTION).ignore(
                ignore_selection
            )
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
