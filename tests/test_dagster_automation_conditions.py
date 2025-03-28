from typing import AbstractSet

from dagster import (
    AssetKey,
    AutomationCondition,
    DagsterInstance,
    asset,
    evaluate_automation_conditions,
    materialize,
)
from dagster._annotations import public
from dagster._core.definitions.asset_key import T_EntityKey
from dagster._core.definitions.base_asset_graph import BaseAssetGraph, BaseAssetNode
from dagster._core.definitions.declarative_automation.operators import (
    AnyDepsCondition,
    DepsAutomationCondition,
)


class CustomAnyDepsCondition(AnyDepsCondition):
    def _get_dep_keys(
        self, key: T_EntityKey, asset_graph: BaseAssetGraph[BaseAssetNode]
    ) -> AbstractSet[AssetKey]:
        # TODO: follow the graph to the closest dbt table ancestors
        dep_keys = asset_graph.get(key).parent_entity_keys

        if self.allow_selection is not None:
            dep_keys &= self.allow_selection.resolve(asset_graph)

        if self.ignore_selection is not None:
            dep_keys -= self.ignore_selection.resolve(asset_graph)

        return dep_keys


class CustomAutomationCondition(AutomationCondition):
    @public
    @staticmethod
    def foo(condition: "AutomationCondition") -> "DepsAutomationCondition":
        return CustomAnyDepsCondition(operand=condition)


test_automation_condition = (
    AutomationCondition.in_latest_time_window()
    & (
        AutomationCondition.newly_missing() | AutomationCondition.any_deps_updated()
    ).since(AutomationCondition.newly_requested() | AutomationCondition.newly_updated())
    & ~AutomationCondition.any_deps_missing()
    & ~AutomationCondition.any_deps_in_progress()
    & ~AutomationCondition.in_progress()
)


def test_foo():
    @asset(automation_condition=test_automation_condition)
    def upstream_table():
        return

    @asset(deps=[upstream_table], automation_condition=test_automation_condition)
    def intermediate_view():
        return

    @asset(deps=[intermediate_view], automation_condition=test_automation_condition)
    def downstream_table():
        return

    instance = DagsterInstance.ephemeral()

    # On the first tick, materialize because assets are missing
    result_1 = evaluate_automation_conditions(
        defs=[upstream_table, intermediate_view, downstream_table], instance=instance
    )
    assert result_1.total_requested == 3

    # Materialize again to simulate further changes
    result = materialize([upstream_table], instance=instance)
    assert result.success

    # Re-evaluate automation conditions
    result_2 = evaluate_automation_conditions(
        defs=[upstream_table, intermediate_view, downstream_table], instance=instance
    )

    assert {downstream_table.key} == {
        r.key for r in result_2.results if r.true_subset.get_internal_bool_value()
    }
