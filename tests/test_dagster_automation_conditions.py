from typing import AbstractSet

from dagster._annotations import public
from dagster._core.definitions.asset_key import AssetKey, T_EntityKey
from dagster._core.definitions.assets.graph.base_asset_graph import (
    BaseAssetGraph,
    BaseAssetNode,
)
from dagster._core.definitions.declarative_automation.automation_condition import (
    AutomationCondition,
    AutomationResult,
)
from dagster._core.definitions.declarative_automation.automation_context import (
    AutomationContext,
)
from dagster._core.definitions.declarative_automation.operators.dep_operators import (
    AnyDepsCondition,
    DepsAutomationCondition,
    EntityMatchesCondition,
)
from dagster_shared import check


class DbtTableAnyDepsCondition(AnyDepsCondition):
    def _get_dep_keys(
        self, key: T_EntityKey, asset_graph: BaseAssetGraph[BaseAssetNode]
    ) -> AbstractSet[AssetKey]:
        dep_keys = set(
            [
                asset_key
                for asset_key in asset_graph.get_ancestor_asset_keys(
                    asset_key=check.inst(obj=key, ttype=AssetKey)
                )
                if asset_graph._asset_nodes_by_key[asset_key].metadata[
                    "dagster-dbt/materialization_type"
                ]
                == "table"
            ]
        )

        if self.allow_selection is not None:
            dep_keys &= self.allow_selection.resolve(asset_graph, allow_missing=True)

        if self.ignore_selection is not None:
            dep_keys -= self.ignore_selection.resolve(asset_graph, allow_missing=True)

        return dep_keys

    async def evaluate(
        self, context: AutomationContext[T_EntityKey]
    ) -> AutomationResult[T_EntityKey]:
        dep_results = []
        true_subset = context.get_empty_subset()

        for i, dep_key in enumerate(
            sorted(self._get_dep_keys(context.key, context.asset_graph))
        ):
            dep_result = await context.for_child_condition(
                child_condition=EntityMatchesCondition(
                    key=dep_key, operand=self.operand
                ),
                # Prefer a non-indexed ID in case asset keys move around, but fall back
                # to the indexed one for back-compat
                child_indices=[None, i],
                candidate_subset=context.candidate_subset,
            ).evaluate_async()

            dep_results.append(dep_result)
            true_subset = true_subset.compute_union(dep_result.true_subset)

        true_subset = context.candidate_subset.compute_intersection(true_subset)

        return AutomationResult(
            context, true_subset=true_subset, child_results=dep_results
        )


class DbtTableAutomationCondition(AutomationCondition):
    @public
    @staticmethod
    def any_deps_match(condition: "AutomationCondition") -> "DepsAutomationCondition":
        """Returns an AutomationCondition that is true for a if at least one partition
        of the any of the target's dependencies evaluate to True for the given
        condition.

        Args:
            condition (AutomationCondition): The AutomationCondition that will be
            evaluated against this target's dependencies.
        """
        return DbtTableAnyDepsCondition(operand=condition)

    @public
    @staticmethod
    def any_deps_updated() -> "DepsAutomationCondition":
        """Returns an AutomationCondition that is true if the target has at least one
        dependency that has updated since the previous tick, or will be requested on
        this tick.

        Will ignore parent updates if the run that updated the parent also plans to
        update the asset or check that this condition is applied to.
        """
        return DbtTableAutomationCondition.any_deps_match(
            (
                AutomationCondition.newly_updated()
                # executed_with_root_target is fairly expensive on a per-partition
                # basis, but newly_updated is bounded in the number of partitions that
                # might be updated on a single tick
                & ~AutomationCondition.executed_with_root_target()
            ).with_label("newly_updated_without_root")
            | AutomationCondition.will_be_requested()
        ).with_label("any_deps_updated")
