from typing import AbstractSet

from dagster import (
    AssetKey,
    AutomationCondition,
    DagsterInstance,
    asset,
    evaluate_automation_conditions,
    materialize,
)

# trunk-ignore-begin(pyright/reportPrivateImportUsage)
from dagster._annotations import public
from dagster._core.definitions.asset_graph import AssetGraph
from dagster._core.definitions.declarative_automation.operators import (
    AnyDepsCondition,
    DepsAutomationCondition,
)

# trunk-ignore-end(pyright/reportPrivateImportUsage)


class DbtTableAnyDepsCondition(AnyDepsCondition):
    # trunk-ignore(pyright/reportIncompatibleMethodOverride)
    def _get_dep_keys(
        self, key: AssetKey, asset_graph: AssetGraph
    ) -> AbstractSet[AssetKey]:
        asset_def = [a.assets_def for a in asset_graph.asset_nodes if a.key == key][0]

        if asset_def.metadata_by_key[key]["dagster-dbt/materialization_type"] == "view":
            return set()

        # TODO: follow the graph to the closest dbt table ancestors
        dep_keys = {
            a.key
            for a in asset_graph.asset_nodes
            for ancestor in asset_graph.get_ancestor_asset_keys(asset_key=key)
            if a.key == ancestor
            and a.assets_def.metadata_by_key[a.key]["dagster-dbt/materialization_type"]
            == "table"
        }

        if self.allow_selection is not None:
            dep_keys &= self.allow_selection.resolve(asset_graph)

        if self.ignore_selection is not None:
            dep_keys -= self.ignore_selection.resolve(asset_graph)

        return dep_keys


class DbtTableAutomationCondition(AutomationCondition):
    @public
    @staticmethod
    def custom_any_deps_match(
        condition: AutomationCondition,
    ) -> DepsAutomationCondition:
        return DbtTableAnyDepsCondition(operand=condition)

    @public
    @staticmethod
    def custom_any_deps_updated() -> DepsAutomationCondition:
        return DbtTableAutomationCondition.custom_any_deps_match(
            (
                AutomationCondition.newly_updated()
                # executed_with_root_target is fairly expensive on a per-partition
                # basis, but newly_updated is bounded in the number of partitions that
                # might be updated on a single tick
                & ~AutomationCondition.executed_with_root_target()
            ).with_label("newly_updated_without_root")
            | AutomationCondition.will_be_requested()
        ).with_label("any_deps_updated")


test_automation_condition = (
    AutomationCondition.in_latest_time_window()
    & (
        AutomationCondition.newly_missing()
        | DbtTableAutomationCondition.custom_any_deps_updated()
    ).since(AutomationCondition.newly_requested() | AutomationCondition.newly_updated())
    & ~AutomationCondition.any_deps_missing()
    & ~AutomationCondition.any_deps_in_progress()
    & ~AutomationCondition.in_progress()
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

    assert {downstream_table.key} == {
        r.key for r in result_2.results if r.true_subset.get_internal_bool_value()
    }
