from typing import AbstractSet

from dagster import AssetSelection, AutomationCondition
from dagster._core.asset_graph_view.entity_subset import EntitySubset
from dagster._core.definitions.asset_key import AssetKey
from dagster._core.definitions.assets.graph.base_asset_graph import (
    BaseAssetGraph,
    BaseAssetNode,
)
from dagster._core.definitions.declarative_automation.automation_context import (
    AutomationContext,
)
from dagster._core.definitions.declarative_automation.operands.subset_automation_condition import (
    SubsetAutomationCondition,
)
from dagster._core.definitions.declarative_automation.operators.dep_operators import (
    DepsAutomationCondition,
)
from dagster._core.definitions.events import AssetKeyPartitionKey
from dagster._record import record
from dagster_shared.serdes import whitelist_for_serdes

_MAX_VIEW_DEPTH = 3
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


@whitelist_for_serdes
@record
class AnyDepsUpdatedSinceSelf(SubsetAutomationCondition):
    """True when any dep has a more recent materialization than this asset.

    Replaces the tick-based ``any_deps_updated().since(newly_updated)`` pattern
    with a direct storage-id comparison that is immune to the SinceCondition
    tick-collision bug (dagster-io/dagster#33587).

    When both ``any_deps_updated`` (trigger) and ``newly_updated`` (reset) fire
    within the same evaluation tick, ``SinceCondition`` unconditionally applies
    the reset — even when the dep update has a more recent wall-clock timestamp
    than the asset's completion.  This condition sidesteps the issue entirely by
    comparing ``storage_id`` ordering, which is monotonically increasing and
    tick-independent.

    The condition is self-resetting: once the asset materialises its
    ``storage_id`` becomes the newest, so no ``.since()`` wrapper is needed.
    ``~in_progress`` on the outer condition prevents duplicate requests while a
    run is in flight.

    Supports looking *through* intermediate views (assets matching
    ``view_selection``) up to ``max_view_depth`` levels.
    """

    ignore_selection: AssetSelection | None = None
    view_selection: AssetSelection | None = None
    max_view_depth: int = _MAX_VIEW_DEPTH

    @property
    def name(self) -> str:
        return "any_deps_updated_since_self"

    @property
    def description(self) -> str:
        return "any dep materialized more recently than this asset"

    def _gather_dep_keys(
        self,
        key: AssetKey,
        asset_graph: BaseAssetGraph,
        ignore_keys: AbstractSet[AssetKey],
        view_keys: AbstractSet[AssetKey],
        depth: int,
        _visited: set[AssetKey] | None = None,
    ) -> AbstractSet[AssetKey]:
        """Gather dep keys, recursing through views up to *depth* levels."""
        if _visited is None:
            _visited = set()

        dep_keys = set(asset_graph.get(key).parent_entity_keys) - ignore_keys
        result = set(dep_keys)

        if depth > 0 and view_keys:
            for dep_key in dep_keys:
                if dep_key in view_keys and dep_key not in _visited:
                    _visited.add(dep_key)
                    result |= self._gather_dep_keys(
                        dep_key,
                        asset_graph,
                        ignore_keys,
                        view_keys,
                        depth - 1,
                        _visited,
                    )

        return result

    async def compute_subset(self, context: AutomationContext) -> EntitySubset:
        queryer = context.asset_graph_view.get_inner_queryer_for_back_compat()
        asset_partition = AssetKeyPartitionKey(context.key)

        my_storage_id = queryer.get_latest_materialization_or_observation_storage_id(
            asset_partition
        )
        if my_storage_id is None:
            # Never materialised — let newly_missing handle the first run.
            return context.get_empty_subset()

        asset_graph = context.asset_graph_view.asset_graph
        ignore_keys = (
            self.ignore_selection.resolve(asset_graph, allow_missing=True)
            if self.ignore_selection is not None
            else set()
        )
        view_keys = (
            self.view_selection.resolve(asset_graph, allow_missing=True)
            if self.view_selection is not None
            else set()
        )

        all_dep_keys = self._gather_dep_keys(
            context.key, asset_graph, ignore_keys, view_keys, self.max_view_depth
        )

        for dep_key in all_dep_keys:
            # Check 1: dep materialised after us (storage-id comparison).
            # This is the primary check and is tick-independent.
            dep_record = queryer.get_latest_materialization_or_observation_record(
                AssetKeyPartitionKey(dep_key), after_cursor=my_storage_id
            )
            if dep_record is not None:
                return context.candidate_subset

            # Check 2: dep will be requested in this evaluation tick.
            # Matches the will_be_requested() semantics in Dagster's built-in
            # any_deps_updated(), enabling same-tick propagation through chains
            # like Table_A → Table_B → View → Table_C (where Table_B hasn't
            # materialised yet but the evaluator has already decided to request it).
            dep_request = context.request_subsets_by_key.get(dep_key)
            if dep_request is not None and not dep_request.is_empty:
                return context.candidate_subset

        return context.get_empty_subset()


def dbt_view_automation_condition(
    ignore_selection: AssetSelection,
) -> AutomationCondition:
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
      no materialization records) and configured ignore_selection to prevent
      them from permanently blocking downstream automation.
    - Filtered any_deps_in_progress: ignores configured ignore_selection.
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
        & ~AutomationCondition.any_deps_missing().ignore(
            ignore_selection | _EXTERNAL_SOURCE_SELECTION
        )
        & ~AutomationCondition.any_deps_in_progress().ignore(ignore_selection)
        & ~AutomationCondition.in_progress()
    )


def dbt_table_automation_condition(
    ignore_selection: AssetSelection,
) -> AutomationCondition:
    """Automation condition for dbt TABLE models.

    Fork of AutomationCondition.eager() adapted for tables, which store
    physical data and must be re-materialized when upstream data changes.

    Changes from eager():
    - Replaced any_deps_updated().since() with AnyDepsUpdatedSinceSelf: uses
      direct storage-id comparison instead of the tick-based SinceCondition,
      fixing a bug where dep updates are silently swallowed when they co-occur
      with the downstream's newly_updated in the same evaluation tick
      (dagster-io/dagster#33587).
    - AnyDepsUpdatedSinceSelf also subsumes the ancestor lookthrough: it
      gathers dep keys through intermediate views (up to _MAX_VIEW_DEPTH
      levels) and checks storage-id ordering for all of them in one pass.
    - Added code_version_changed: detects SQL code changes from dbt deploys.
      Uses its own .since(newly_updated) so it only resets after successful
      materialization, not on request — the signal isn't lost if the run
      fails or never executes.
    - Filtered any_deps_missing: ignores external source assets (which have
      no materialization records) and configured ignore_selection to prevent
      them from permanently blocking downstream automation.
    - Filtered any_deps_in_progress: ignores configured ignore_selection.
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
            | AnyDepsUpdatedSinceSelf(
                ignore_selection=ignore_selection,
                view_selection=_VIEW_SELECTION,
                max_view_depth=_MAX_VIEW_DEPTH,
            )
            | AutomationCondition.code_version_changed().since(
                AutomationCondition.newly_updated()
            )
            | AutomationCondition.execution_failed()
        )
        & ~AutomationCondition.any_deps_missing().ignore(
            ignore_selection | _EXTERNAL_SOURCE_SELECTION
        )
        & ~AutomationCondition.any_deps_in_progress().ignore(ignore_selection)
        & ~AutomationCondition.in_progress()
    )
