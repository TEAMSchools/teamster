from typing import Any, Mapping

from dagster import AssetKey, AutomationCondition
from dagster_dbt import DagsterDbtTranslator, DagsterDbtTranslatorSettings


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

        if not automation_condition_config.get("enabled", True):
            return None
        elif (
            dbt_resource_props["resource_type"] == "model"
            and dbt_resource_props["config"]["materialized"] == "view"
            and "extracts" in dbt_resource_props["fqn"]
        ):
            return (
                AutomationCondition.code_version_changed()
                | AutomationCondition.newly_missing()
            )
        else:
            return (
                AutomationCondition.eager() | AutomationCondition.code_version_changed()
            )

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
