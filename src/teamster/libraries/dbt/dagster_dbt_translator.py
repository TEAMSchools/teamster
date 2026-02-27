from typing import Any, Mapping

from dagster import AssetKey, AssetSelection, AutomationCondition
from dagster_dbt import DagsterDbtTranslator, DagsterDbtTranslatorSettings

from teamster.core.automation_conditions import (
    dbt_table_automation_condition,
    dbt_view_automation_condition,
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

        materialized = dbt_resource_props.get("config", {}).get("materialized", "view")

        if materialized == "view":
            return dbt_view_automation_condition(
                ignore_selection=ignore_selection,
            )
        else:
            return dbt_table_automation_condition(
                ignore_selection=ignore_selection,
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
