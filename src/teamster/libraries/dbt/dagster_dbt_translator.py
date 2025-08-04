from typing import AbstractSet, Any, Mapping

from dagster import AssetKey, AssetSelection, AutomationCondition
from dagster._annotations import public
from dagster._core.definitions.asset_key import T_EntityKey
from dagster._core.definitions.assets.graph.base_asset_graph import (
    BaseAssetGraph,
    BaseAssetNode,
)
from dagster._core.definitions.declarative_automation.operators.dep_operators import (
    AnyDepsCondition,
    DepsAutomationCondition,
)
from dagster_dbt import DagsterDbtTranslator, DagsterDbtTranslatorSettings
from dagster_shared import check


class DbtTableAnyDepsCondition(AnyDepsCondition):
    def _get_dep_keys(
        self, key: T_EntityKey, asset_graph: BaseAssetGraph[BaseAssetNode]
    ) -> AbstractSet[AssetKey]:
        dep_keys = asset_graph.get_ancestor_asset_keys(
            asset_key=check.inst(obj=key, ttype=AssetKey)
        )

        if self.allow_selection is not None:
            dep_keys &= self.allow_selection.resolve(asset_graph, allow_missing=True)

        if self.ignore_selection is not None:
            dep_keys -= self.ignore_selection.resolve(asset_graph, allow_missing=True)

        return dep_keys


class DbtTableAutomationCondition(AutomationCondition):
    @public
    @staticmethod
    def any_deps_match(condition: "AutomationCondition") -> "DepsAutomationCondition":
        return DbtTableAnyDepsCondition(operand=condition)

    @public
    @staticmethod
    def any_deps_updated() -> "DepsAutomationCondition":
        return DbtTableAutomationCondition.any_deps_match(
            (
                DbtTableAutomationCondition.newly_updated()
                & ~DbtTableAutomationCondition.executed_with_root_target()
            ).with_label("newly_updated_without_root")
            | DbtTableAutomationCondition.will_be_requested()
        ).with_label("any_deps_updated")


def get_view_automation_condition(selection):
    """forked from AutomationCondition.eager()
    - add code_version_changed()
    - add ignore external assets
    - replace since_last_handled() to allow initial_evaluation()
    - remove any_deps_updated()
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
            selection
            | (
                AssetSelection.all(include_sources=True)
                - AssetSelection.all(include_sources=False)
            )
        )
        & ~AutomationCondition.any_deps_in_progress().ignore(selection)
        & ~AutomationCondition.in_progress()
    )


def get_table_automation_condition(selection):
    """forked from AutomationCondition.eager()
    - add code_version_changed()
    - add ignore external assets
    - replace since_last_handled() to allow initial_evaluation()
    - add ignore on any_deps_updated()
    """

    return (
        DbtTableAutomationCondition.in_latest_time_window()
        & (
            DbtTableAutomationCondition.newly_missing()
            | DbtTableAutomationCondition.code_version_changed()
            | DbtTableAutomationCondition.any_deps_updated().ignore(selection)
        )
        # .since(
        #     DbtTableAutomationCondition.newly_requested()
        #     | DbtTableAutomationCondition.newly_updated()
        # )
        # & ~DbtTableAutomationCondition.any_deps_missing().ignore(
        #     selection
        #     | (
        #         AssetSelection.all(include_sources=True)
        #         - AssetSelection.all(include_sources=False)
        #     )
        # )
        # & ~DbtTableAutomationCondition.any_deps_in_progress().ignore(selection)
        # & ~DbtTableAutomationCondition.in_progress()
    )


class CustomDagsterDbtTranslator(DagsterDbtTranslator):
    def __init__(
        self, code_location: str, settings: DagsterDbtTranslatorSettings | None = None
    ):
        self.code_location = code_location

        super().__init__(settings)

    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        asset_key = super().get_asset_key(dbt_resource_props)

        dbt_meta = dbt_resource_props.get("config", {}).get(
            "meta", {}
        ) or dbt_resource_props.get("meta", {})

        if dbt_meta.get("dagster", {}).get("asset_key", []):
            return asset_key
        else:
            return asset_key.with_prefix(self.code_location)

    def get_automation_condition(
        self, dbt_resource_props: Mapping[str, Any]
    ) -> AutomationCondition | None:
        dagster_metadata: dict = dbt_resource_props.get("meta", {}).get("dagster", {})

        automation_condition_config: dict = dagster_metadata.get(
            "automation_condition", {}
        )

        ignore_selection = AssetSelection.keys(
            *automation_condition_config.get("ignore", {}).get("keys", {})
        )

        if not automation_condition_config.get("enabled", True):
            return None
        elif (
            dbt_resource_props["resource_type"] == "model"
            and dbt_resource_props["config"]["materialized"] == "view"
        ):
            return get_view_automation_condition(ignore_selection)
        else:
            return get_table_automation_condition(ignore_selection)

    def get_group_name(self, dbt_resource_props: Mapping[str, Any]) -> str | None:
        group = super().get_group_name(dbt_resource_props)

        package_name = dbt_resource_props["package_name"]
        fqn_1 = dbt_resource_props["fqn"][1]

        if group is not None:
            return group
        elif package_name == self.code_location:
            return fqn_1
        elif package_name is None:
            return fqn_1
        else:
            return package_name
