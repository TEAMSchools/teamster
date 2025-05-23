from abc import abstractmethod
from typing import AbstractSet, Any, Generic, Sequence

from dagster import (
    AssetKey,
    AssetSelection,
    AutomationCondition,
    AutomationContext,
    AutomationResult,
    DagsterInstance,
    asset,
    evaluate_automation_conditions,
    materialize,
)
from dagster._annotations import public
from dagster._core.asset_graph_view.asset_graph_view import U_EntityKey
from dagster._core.definitions.asset_key import T_EntityKey
from dagster._core.definitions.base_asset_graph import BaseAssetGraph, BaseAssetNode
from dagster._core.definitions.declarative_automation.automation_condition import (
    BuiltinAutomationCondition,
)
from dagster._core.definitions.declarative_automation.serialized_objects import (
    OperatorType,
)
from dagster._record import copy, record
from dagster._utils.security import non_secure_md5_hash_str
from dagster_shared import check


@record
class DbtTableDepsAutomationCondition(BuiltinAutomationCondition[T_EntityKey]):
    operand: AutomationCondition

    # Should be AssetSelection, but this causes circular reference issues
    allow_selection: Any | None = None
    ignore_selection: Any | None = None

    @property
    @abstractmethod
    def base_name(self) -> str: ...

    @property
    def name(self) -> str:
        name = self.base_name
        props = []

        if self.allow_selection is not None:
            props.append(f"allow_selection={self.allow_selection}")

        if self.ignore_selection is not None:
            props.append(f"ignore_selection={self.ignore_selection}")

        if props:
            name += f"({','.join(props)})"

        return name

    @property
    def requires_cursor(self) -> bool:
        return False

    def get_node_unique_id(
        self, *, parent_unique_id: str | None, index: int | None
    ) -> str:
        """Ignore allow_selection / ignore_selection for the cursor hash."""
        parts = [str(parent_unique_id), str(index), self.base_name]

        return non_secure_md5_hash_str("".join(parts).encode())

    def get_backcompat_node_unique_ids(
        self, *, parent_unique_id: str | None = None, index: int | None = None
    ) -> Sequence[str]:
        # backcompat for previous cursors where the allow/ignore selection influenced
        # the hash
        return [
            super().get_node_unique_id(parent_unique_id=parent_unique_id, index=index)
        ]

    @public
    def allow(self, selection: "AssetSelection") -> "DbtTableDepsAutomationCondition":
        """Returns a copy of this condition that will only consider dependencies within
        the provided AssetSelection.
        """
        from dagster._core.definitions.asset_selection import AssetSelection

        check.inst_param(selection, "selection", AssetSelection)

        allow_selection = (
            selection
            if self.allow_selection is None
            else selection | self.allow_selection
        )

        return copy(self, allow_selection=allow_selection)

    @public
    def ignore(self, selection: "AssetSelection") -> "DbtTableDepsAutomationCondition":
        """Returns a copy of this condition that will ignore dependencies within the
        provided AssetSelection.
        """
        from dagster._core.definitions.asset_selection import AssetSelection

        check.inst_param(selection, "selection", AssetSelection)

        ignore_selection = (
            selection
            if self.ignore_selection is None
            else selection | self.ignore_selection
        )

        return copy(self, ignore_selection=ignore_selection)

    def _get_dep_keys(
        self, key: T_EntityKey, asset_graph: BaseAssetGraph[BaseAssetNode]
    ) -> AbstractSet[AssetKey]:
        dep_keys = asset_graph.get(key).parent_entity_keys

        if self.allow_selection is not None:
            dep_keys &= self.allow_selection.resolve(asset_graph, allow_missing=True)

        if self.ignore_selection is not None:
            dep_keys -= self.ignore_selection.resolve(asset_graph, allow_missing=True)

        return dep_keys

    @public
    def replace(
        self, old: AutomationCondition | str, new: AutomationCondition
    ) -> AutomationCondition:
        """Replaces all instances of ``old`` across any sub-conditions with ``new``.

        If ``old`` is a string, then conditions with a label matching
        that string will be replaced.

        Args:
            old (Union[AutomationCondition, str]): The condition to replace.
            new (AutomationCondition): The condition to replace with.
        """
        return (
            new
            if old in [self, self.get_label()]
            else copy(self, operand=self.operand.replace(old, new))
        )


class DbtTableAnyDepsCondition(DbtTableDepsAutomationCondition[T_EntityKey]):
    @property
    def base_name(self) -> str:
        return "ANY_DEPS_MATCH"

    @property
    def operator_type(self) -> OperatorType:
        return "or"

    # trunk-ignore(pyright/reportIncompatibleMethodOverride)
    async def evaluate(
        self, context: AutomationContext[T_EntityKey]
    ) -> AutomationResult[T_EntityKey]:
        dep_results = []
        true_subset = context.get_empty_subset()

        for i, dep_key in enumerate(
            sorted(self._get_dep_keys(context.key, context.asset_graph))
        ):
            dep_result = await context.for_child_condition(
                child_condition=DbtTableEntityMatchesCondition(
                    key=dep_key, operand=self.operand
                ),
                # Prefer a non-indexed ID in case asset keys move around, but fall back
                # to the indexed one for back-compat
                child_indices=[
                    None,
                    i,
                ],
                candidate_subset=context.candidate_subset,
            ).evaluate_async()

            dep_results.append(dep_result)

            true_subset = true_subset.compute_union(dep_result.true_subset)

        true_subset = context.candidate_subset.compute_intersection(true_subset)

        return AutomationResult(
            context, true_subset=true_subset, child_results=dep_results
        )

    # def _get_dep_keys(
    #     self, key: AssetKey, asset_graph: AssetGraph
    # ) -> AbstractSet[AssetKey]:
    #     asset_def = [a.assets_def for a in asset_graph.asset_nodes if a.key == key][0]

    #     if asset_def.metadata_by_key[key]["dagster-dbt/materialization_type"] == "view":
    #         return set()

    #     # TODO: follow the graph to the closest dbt table ancestors
    #     dep_keys = {
    #         a.key
    #         for a in asset_graph.asset_nodes
    #         for ancestor in asset_graph.get_ancestor_asset_keys(asset_key=key)
    #         if a.key == ancestor
    #         and a.assets_def.metadata_by_key[a.key]["dagster-dbt/materialization_type"]
    #         == "table"
    #     }

    #     if self.allow_selection is not None:
    #         dep_keys &= self.allow_selection.resolve(asset_graph)

    #     if self.ignore_selection is not None:
    #         dep_keys -= self.ignore_selection.resolve(asset_graph)

    #     return dep_keys


@record
class DbtTableEntityMatchesCondition(
    BuiltinAutomationCondition[T_EntityKey], Generic[T_EntityKey, U_EntityKey]
):
    key: U_EntityKey
    operand: AutomationCondition[U_EntityKey]

    @property
    def name(self) -> str:
        return self.key.to_user_string()

    # trunk-ignore(pyright/reportIncompatibleMethodOverride)
    async def evaluate(
        self, context: AutomationContext[T_EntityKey]
    ) -> AutomationResult[T_EntityKey]:
        # if the key we're mapping to is a child of the key we're mapping from and is
        # not self-dependent, use the downstream mapping function, otherwise use
        # upstream
        if (
            self.key in context.asset_graph.get(context.key).child_entity_keys
            and self.key != context.key
        ):
            directions = ("down", "up")
        else:
            directions = ("up", "down")

        to_candidate_subset = context.candidate_subset.compute_mapped_subset(
            self.key, direction=directions[0]
        )

        to_context = context.for_child_condition(
            child_condition=self.operand,
            child_indices=[0],
            candidate_subset=to_candidate_subset,
        )

        to_result = await to_context.evaluate_async()

        true_subset = to_result.true_subset.compute_mapped_subset(
            context.key, direction=directions[1]
        )

        return AutomationResult(
            context=context, true_subset=true_subset, child_results=[to_result]
        )

    @public
    def replace(
        self, old: AutomationCondition | str, new: AutomationCondition
    ) -> AutomationCondition:
        """Replaces all instances of ``old`` across any sub-conditions with ``new``.

        If ``old`` is a string, then conditions with a label matching that string will
        be replaced.

        Args:
            old (Union[AutomationCondition, str]): The condition to replace.
            new (AutomationCondition): The condition to replace with.
        """
        return (
            new
            if old in [self, self.get_label()]
            else copy(self, operand=self.operand.replace(old, new))
        )


class DbtTableAutomationCondition(AutomationCondition):
    # @public
    # @staticmethod
    # def custom_any_deps_match(
    #     condition: "DbtTableAutomationCondition",
    # ) -> DbtTableDepsAutomationCondition:
    #     return DbtTableAnyDepsCondition(operand=condition)

    # @public
    # @staticmethod
    # def custom_any_deps_updated() -> DbtTableDepsAutomationCondition:
    #     return DbtTableAutomationCondition.custom_any_deps_match(
    #         (
    #             DbtTableAutomationCondition.newly_updated()
    #             # executed_with_root_target is fairly expensive on a per-partition
    #             # basis, but newly_updated is bounded in the number of partitions that
    #             # might be updated on a single tick
    #             & ~DbtTableAutomationCondition.executed_with_root_target()
    #         ).with_label("newly_updated_without_root")
    #         | DbtTableAutomationCondition.will_be_requested()
    #     ).with_label("any_deps_updated")

    @public
    @staticmethod
    # trunk-ignore(pyright/reportIncompatibleMethodOverride)
    def any_deps_match(
        condition: "DbtTableAutomationCondition",
    ) -> "DbtTableDepsAutomationCondition":
        """Returns an AutomationCondition that is true for a if at least one partition
        of the any of the target's dependencies evaluate to True for the given
        condition.

        Args:
            condition (AutomationCondition): The AutomationCondition that will be
            evaluated against
                this target's dependencies.
        """
        return DbtTableAnyDepsCondition(operand=condition)

    @public
    @staticmethod
    # trunk-ignore(pyright/reportIncompatibleMethodOverride)
    def any_deps_updated() -> DbtTableDepsAutomationCondition:
        return DbtTableAutomationCondition.any_deps_match(
            # trunk-ignore(pyright/reportArgumentType)
            (
                DbtTableAutomationCondition.newly_updated()
                # executed_with_root_target is fairly expensive on a per-partition
                # basis, but newly_updated is bounded in the number of partitions that
                # might be updated on a single tick
                & ~DbtTableAutomationCondition.executed_with_root_target()
            ).with_label("newly_updated_without_root")
            | DbtTableAutomationCondition.will_be_requested()
        ).with_label("any_deps_updated")


test_automation_condition = (
    DbtTableAutomationCondition.in_latest_time_window()
    & (
        DbtTableAutomationCondition.newly_missing()
        | DbtTableAutomationCondition.any_deps_updated()
    ).since_last_handled()
    & ~DbtTableAutomationCondition.any_deps_missing()
    & ~DbtTableAutomationCondition.any_deps_in_progress()
    & ~DbtTableAutomationCondition.in_progress()
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
