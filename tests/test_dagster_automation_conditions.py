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
from dagster._core.definitions.asset_graph import AssetNode
from dagster._core.definitions.asset_key import T_EntityKey
from dagster._core.definitions.base_asset_graph import BaseAssetGraph, BaseAssetNode
from dagster._core.definitions.declarative_automation.operators import AnyDepsCondition
from dagster._core.definitions.declarative_automation.operators.dep_operators import (
    DepsAutomationCondition,
)


class DbtDepsAutomationCondition(DepsAutomationCondition):
    def _get_dep_keys(
        self, key: T_EntityKey, asset_graph: BaseAssetGraph[BaseAssetNode]
    ) -> AbstractSet[AssetKey]:
        asset_def = [
            a.assets_def
            for a in asset_graph.asset_nodes
            if isinstance(a, AssetNode) and a.key == key
        ][0]

        if (
            isinstance(key, AssetKey)
            and asset_def.metadata_by_key[key]["dagster-dbt/materialization_type"]
            == "table"
        ):
            dep_keys = asset_graph.get_ancestor_asset_keys(asset_key=key)
        else:
            dep_keys = asset_graph.get(key).parent_entity_keys

        if self.allow_selection is not None:
            dep_keys &= self.allow_selection.resolve(
                all_assets=asset_graph, allow_missing=True
            )

        if self.ignore_selection is not None:
            dep_keys -= self.ignore_selection.resolve(
                all_assets=asset_graph, allow_missing=True
            )

        return dep_keys


class DbtAnyDepsCondition(DbtDepsAutomationCondition, AnyDepsCondition): ...


class DbtAutomationCondition(AutomationCondition):
    @public
    @staticmethod
    # trunk-ignore(pyright/reportIncompatibleMethodOverride)
    def any_deps_match(
        condition: "DbtAutomationCondition",
    ) -> "DbtDepsAutomationCondition":
        """Returns an AutomationCondition that is true for a if at least one partition
        of the any of the target's dependencies evaluate to True for the given
        condition.

        Args:
            condition (AutomationCondition): The AutomationCondition that will be
            evaluated against
                this target's dependencies.
        """
        return DbtAnyDepsCondition(operand=condition)

    @public
    @staticmethod
    def any_deps_updated() -> DbtDepsAutomationCondition:
        return DbtAutomationCondition.any_deps_match(
            (
                DbtAutomationCondition.newly_updated()
                # executed_with_root_target is fairly expensive on a per-partition
                # basis, but newly_updated is bounded in the number of partitions that
                # might be updated on a single tick
                & ~DbtAutomationCondition.executed_with_root_target()
            ).with_label("newly_updated_without_root")
            | DbtAutomationCondition.will_be_requested()
        ).with_label("any_deps_updated")


test_automation_condition = (
    DbtAutomationCondition.in_latest_time_window()
    & (
        DbtAutomationCondition.newly_missing()
        | DbtAutomationCondition.any_deps_updated()
        | DbtAutomationCondition.code_version_changed()
    ).since(AutomationCondition.newly_requested() | AutomationCondition.newly_updated())
    & ~DbtAutomationCondition.any_deps_missing()
    & ~DbtAutomationCondition.any_deps_in_progress()
    & ~DbtAutomationCondition.in_progress()
)


def test_foo():
    @asset(
        automation_condition=test_automation_condition,
        metadata={"dagster-dbt/materialization_type": "table"},
    )
    def upstream_table():
        return

    @asset(
        deps=[upstream_table],
        automation_condition=test_automation_condition,
        metadata={"dagster-dbt/materialization_type": "view"},
    )
    def intermediate_view():
        return

    @asset(
        deps=[intermediate_view],
        automation_condition=test_automation_condition,
        metadata={"dagster-dbt/materialization_type": "table"},
    )
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

    assert result_2.total_requested == 1
    assert {
        r.key for r in result_2.results if r.true_subset.get_internal_bool_value()
    } == {downstream_table.key}
