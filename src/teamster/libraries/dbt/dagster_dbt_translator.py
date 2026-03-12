from collections.abc import Mapping
from typing import Any

from dagster import AssetKey, AutomationCondition
from dagster_dbt import DagsterDbtTranslator, DagsterDbtTranslatorSettings

from teamster.core.automation_conditions import (
    dbt_table_automation_condition,
    dbt_view_automation_condition,
)


class CustomDagsterDbtTranslator(DagsterDbtTranslator):
    def __init__(
        self, code_location: str, settings: DagsterDbtTranslatorSettings | None = None
    ) -> None:
        self.code_location = code_location

        super().__init__(settings)

    def get_tags(self, dbt_resource_props: Mapping[str, Any]) -> Mapping[str, str]:
        tags = super().get_tags(dbt_resource_props)
        materialized = dbt_resource_props.get("config", {}).get("materialized", "view")
        return {**tags, "dagster/materialized": materialized}

    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        asset_key = super().get_asset_key(dbt_resource_props)

        dbt_meta = dbt_resource_props.get("config", {}).get(
            "meta", {}
        ) or dbt_resource_props.get("meta", {})

        if dbt_meta.get("dagster", {}).get("asset_key", []):
            return asset_key

        return asset_key.with_prefix(self.code_location)

    def get_automation_condition(
        self, dbt_resource_props: Mapping[str, Any]
    ) -> AutomationCondition | None:
        automation_condition_config: dict[str, Any] = (
            dbt_resource_props.get("meta", {})
            .get("dagster", {})
            .get("automation_condition", {})
        )

        if not automation_condition_config.get("enabled", True):
            return None

        materialized = dbt_resource_props.get("config", {}).get("materialized", "view")

        if materialized in ["view", "ephemeral"]:
            return dbt_view_automation_condition()
        else:
            return dbt_table_automation_condition()

    def get_group_name(self, dbt_resource_props: Mapping[str, Any]) -> str | None:
        group = super().get_group_name(dbt_resource_props)

        if group is not None:
            return group

        package_name = dbt_resource_props["package_name"]

        if package_name is not None and package_name != self.code_location:
            return package_name

        return dbt_resource_props["fqn"][1]
