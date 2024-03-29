from typing import Any, Mapping, Optional

from dagster import AssetKey
from dagster_dbt import KeyPrefixDagsterDbtTranslator
from dagster_dbt.asset_utils import default_group_from_dbt_resource_props


class CustomDagsterDbtTranslator(KeyPrefixDagsterDbtTranslator):
    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        asset_key = super().get_asset_key(dbt_resource_props)

        asset_key.path.insert(-1, "dbt")

        return asset_key

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
