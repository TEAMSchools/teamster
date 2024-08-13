from typing import Any, Mapping

from dagster import AssetKey, AutoMaterializePolicy
from dagster_dbt import DagsterDbtTranslator, DagsterDbtTranslatorSettings
from dagster_dbt.asset_utils import default_group_from_dbt_resource_props


class CustomDagsterDbtTranslator(DagsterDbtTranslator):
    def __init__(
        self, code_location: str, settings: DagsterDbtTranslatorSettings | None = None
    ):
        self.code_location = code_location

        super().__init__(settings)

    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        dbt_meta = dbt_resource_props.get("config", {}).get(
            "meta", {}
        ) or dbt_resource_props.get("meta", {})

        dagster_metadata = dbt_meta.get("dagster", {})

        asset_key_config = dagster_metadata.get("asset_key", [])

        if asset_key_config:
            return AssetKey(asset_key_config)

        if dbt_resource_props["resource_type"] == "source":
            components = [dbt_resource_props["source_name"], dbt_resource_props["name"]]
        elif dbt_resource_props.get("version"):
            components = [dbt_resource_props["alias"]]
        else:
            configured_schema = dbt_resource_props["config"].get("schema")
            if configured_schema is not None:
                components = [configured_schema, dbt_resource_props["name"]]
            else:
                components = [dbt_resource_props["name"]]

        return AssetKey([self.code_location, *components])

    def get_auto_materialize_policy(
        self, dbt_resource_props: Mapping[str, Any]
    ) -> AutoMaterializePolicy | None:
        dagster_metadata = dbt_resource_props.get("meta", {}).get("dagster", {})

        auto_materialize_policy_config = dagster_metadata.get(
            "auto_materialize_policy", {}
        )

        amp_type = auto_materialize_policy_config.get("type")

        if amp_type == "none":
            return None
        elif amp_type == "lazy":
            return AutoMaterializePolicy.lazy()
        else:
            return AutoMaterializePolicy.eager(
                auto_materialize_policy_config.get("max_materializations_per_minute")
            )

    def get_group_name(self, dbt_resource_props: Mapping[str, Any]) -> str | None:
        group = default_group_from_dbt_resource_props(dbt_resource_props)

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
