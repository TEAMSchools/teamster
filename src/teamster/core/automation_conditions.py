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

_MAX_VIEW_DEPTH = 10
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


# TODO: remove when dagster > 1.9.12 fixes _get_dep_keys
DepsAutomationCondition._get_dep_keys = _patched_get_dep_keys


_EXTERNAL_SOURCE_SELECTION = AssetSelection.all(
    include_sources=True
) - AssetSelection.all(include_sources=False)


def _build_any_ancestor_updated(
    max_depth: int = _MAX_VIEW_DEPTH, view_selection: AssetSelection | None = None
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

    for _ in range(max_depth - 1):
        recurse = AutomationCondition.any_deps_match(condition)

        if view_selection is not None:
            recurse = recurse.allow(view_selection)

        condition = AutomationCondition.any_deps_updated() | recurse

    return AutomationCondition.any_deps_match(condition)


def dbt_view_automation_condition() -> AutomationCondition:
    """Automation condition for dbt VIEW models.

    Fork of AutomationCondition.eager() adapted for views, which are computed
    on read and don't store physical data.

    Changes from eager():
    - Removed any_deps_updated: views don't need re-materialization when
      upstream data changes, only when their own definition changes.
    - Added code_version_changed: detects SQL code changes from dbt deploys.
      Uses its own .since(newly_updated) so it only resets after successful
      materialization, not on request — the signal isn't lost if the run
      fails or never executes.
    - Added execution_failed: retries views whose last execution failed,
      evaluated outside .since() so it fires every tick until resolved.
    - Filtered any_deps_missing: ignores external source assets (which have
      no materialization records) to prevent them from permanently blocking
      downstream automation.
    - Omitted initial_evaluation from .since() reset: it fires on the same
      tick as newly_missing, suppressing it permanently since newly_missing
      is event-like and never re-fires.
    """
    _since_last_handled = (
        AutomationCondition.newly_requested() | AutomationCondition.newly_updated()
    )

    return (
        AutomationCondition.in_latest_time_window()
        & (
            AutomationCondition.newly_missing().since(_since_last_handled)
            | AutomationCondition.code_version_changed().since(
                AutomationCondition.newly_updated()
            )
            | AutomationCondition.execution_failed()
        )
        & ~AutomationCondition.any_deps_missing().ignore(_EXTERNAL_SOURCE_SELECTION)
        & ~AutomationCondition.any_deps_in_progress()
        & ~AutomationCondition.in_progress()
    )


def dbt_table_automation_condition() -> AutomationCondition:
    """Automation condition for dbt TABLE models.

    Fork of AutomationCondition.eager() adapted for tables, which store
    physical data and must be re-materialized when upstream data changes.

    Changes from eager():
    - Added ancestor lookthrough: uses recursive any_deps_match (up to
      _MAX_VIEW_DEPTH levels) to detect upstream table updates through
      intermediate views that aren't re-materialized.
    - Added code_version_changed: detects SQL code changes from dbt deploys.
      Uses its own .since(newly_updated) so it only resets after successful
      materialization, not on request — the signal isn't lost if the run
      fails or never executes.
    - Filtered any_deps_missing: ignores external source assets (which have
      no materialization records) to prevent them from permanently blocking
      downstream automation.
    - Omitted initial_evaluation from .since() reset: it fires on the same
      tick as newly_missing, suppressing it permanently since newly_missing
      is event-like and never re-fires.
    """
    _since_last_handled = (
        AutomationCondition.newly_requested() | AutomationCondition.newly_updated()
    )

    return (
        AutomationCondition.in_latest_time_window()
        & (
            (
                AutomationCondition.newly_missing()
                | AutomationCondition.any_deps_updated()
                | _build_any_ancestor_updated(view_selection=_VIEW_SELECTION)
            ).since(_since_last_handled)
            | AutomationCondition.code_version_changed().since(
                AutomationCondition.newly_updated()
            )
            | AutomationCondition.execution_failed()
        )
        & ~AutomationCondition.any_deps_missing().ignore(_EXTERNAL_SOURCE_SELECTION)
        & ~AutomationCondition.any_deps_in_progress()
        & ~AutomationCondition.in_progress()
    )
