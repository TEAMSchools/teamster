from typing import Any, Mapping, Optional

from dagster_dbt import KeyPrefixDagsterDbtTranslator
from dagster_dbt.asset_utils import default_group_from_dbt_resource_props


class CustomDagsterDbtTranslator(KeyPrefixDagsterDbtTranslator):
    # def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
    #     asset_key_config = (
    #         dbt_resource_props.get("meta", {}).get("dagster", {}).get("asset_key", [])
    #     )

    #     if asset_key_config:
    #         return AssetKey(asset_key_config)
    #     else:
    #         return super().get_asset_key(dbt_resource_props)

    # def get_auto_materialize_policy(
    #     self, dbt_resource_props: Mapping[str, Any]
    # ) -> Optional[AutoMaterializePolicy]:
    #     auto_materialize_policy = _auto_materialize_policy_fn(
    #         dbt_resource_props.get("meta", {})
    #         .get("dagster", {})
    #         .get("auto_materialize_policy", {})
    #     )

    #     if auto_materialize_policy:
    #         return auto_materialize_policy
    #     else:
    #         return AutoMaterializePolicy.eager()

    def get_group_name(self, dbt_resource_props: Mapping[str, Any]) -> Optional[str]:
        code_location = self._asset_key_prefix[0]

        group = default_group_from_dbt_resource_props(dbt_resource_props)
        package_name = dbt_resource_props["package_name"]
        fqn_1 = dbt_resource_props["fqn"][1]

        if group is not None:
            return group
        elif package_name == code_location:
            return fqn_1
        elif package_name is None:
            return fqn_1
        else:
            return package_name
