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

_EXTERNAL_SOURCE_SELECTION = AssetSelection.all(
    include_sources=True
) - AssetSelection.all(include_sources=False)

_SINCE_LAST_HANDLED = (
    AutomationCondition.newly_requested() | AutomationCondition.newly_updated()
)


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


def _build_dbt_condition(
    *extra_triggers: AutomationCondition,
) -> AutomationCondition:
    """Build a dbt automation condition with the shared structure.

    All three dbt conditions (view, union_relations, table) share the same
    skeleton — they differ only in what additional triggers (beyond
    newly_missing) cause a materialization request.

    The shared structure is a fork of AutomationCondition.eager() with:
    - code_version_changed on its own .since(newly_updated) so it only resets
      after successful materialization, not on request
    - execution_failed outside .since() so it fires every tick until resolved
    - any_deps_missing ignoring external source assets
    - initial_evaluation omitted from .since() reset to avoid suppressing
      newly_missing permanently
    """
    triggers: AutomationCondition = AutomationCondition.newly_missing()
    for trigger in extra_triggers:
        triggers = triggers | trigger

    return (
        AutomationCondition.in_latest_time_window()
        & (
            triggers.since(_SINCE_LAST_HANDLED)
            | AutomationCondition.code_version_changed().since(
                AutomationCondition.newly_updated()
            )
            | AutomationCondition.execution_failed()
        )
        & ~AutomationCondition.any_deps_missing().ignore(_EXTERNAL_SOURCE_SELECTION)
        & ~AutomationCondition.any_deps_in_progress()
        & ~AutomationCondition.in_progress()
    )


def _build_any_ancestor_updated(
    max_depth: int = _MAX_VIEW_DEPTH, view_selection: AssetSelection | None = None
) -> AutomationCondition:
    """Detect updates in ancestor assets, including through intermediate views.

    Covers all depths:
    - Direct deps: any_deps_updated() detects when a direct dep is updated
    - Ancestors through views: recursive any_deps_match (up to max_depth
      levels) detects when a grandparent+ asset is updated through a chain
      of intermediate views that weren't re-materialized

    For a chain like Table_A -> View_1 -> ... -> View_N -> Table_B,
    this condition on Table_B detects when Table_A is updated.

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

    return AutomationCondition.any_deps_updated() | AutomationCondition.any_deps_match(
        condition
    )


def _build_any_ancestor_code_version_changed(
    max_depth: int = _MAX_VIEW_DEPTH,
) -> AutomationCondition:
    """Detect code version changes in ancestor assets.

    For a chain like Table_A -> View_1 -> ... -> View_N -> union_view, this
    detects when Table_A's raw SQL changes (e.g., a column is added to a
    staging model), even through intermediate views.

    Unlike _build_any_ancestor_updated, this does NOT restrict recursion with
    view_selection. code_version_changed() is self-referential (checks the
    asset's own code version), not dep-relative like any_deps_updated().
    Restricting to view deps would filter out the table whose code version
    actually changed.
    """
    condition = AutomationCondition.code_version_changed()

    for _ in range(max_depth - 1):
        condition = (
            AutomationCondition.code_version_changed()
            | AutomationCondition.any_deps_match(condition)
        )

    return AutomationCondition.any_deps_match(condition)


def dbt_view_automation_condition() -> AutomationCondition:
    """Automation condition for dbt VIEW models.

    Views are computed on read and don't store physical data. Only re-runs
    when the view's own definition changes — NOT on upstream data changes.

    Triggers: newly_missing, code_version_changed, execution_failed.
    """
    return _build_dbt_condition()


def dbt_union_relations_automation_condition() -> AutomationCondition:
    """Automation condition for dbt views using the union_relations macro.

    These views have compiled SQL that resolves column lists at run time.
    Because code_version is a SHA1 of raw_code (the Jinja source), not
    compiled SQL, the view's own code_version_changed won't fire when the
    macro output changes due to upstream schema changes.

    Adds recursive ancestor code_version_changed detection: when an upstream
    model's raw SQL changes after a deploy, this view re-runs so the macro
    recompiles with the updated column set.

    Does NOT trigger on upstream data changes (any_deps_updated) to avoid
    unnecessary Dagster credit and Kubernetes resource costs.
    """
    return _build_dbt_condition(_build_any_ancestor_code_version_changed())


def dbt_table_automation_condition() -> AutomationCondition:
    """Automation condition for dbt TABLE models.

    Tables store physical data and must re-materialize when upstream changes.

    Adds ancestor update detection: recursive any_deps_match (up to
    _MAX_VIEW_DEPTH levels) detects upstream table updates through
    intermediate views that aren't re-materialized.

    Triggers: newly_missing, any_deps_updated (direct + through views),
    code_version_changed, execution_failed.
    """
    return _build_dbt_condition(
        _build_any_ancestor_updated(view_selection=_VIEW_SELECTION)
    )
