from typing import Any, Mapping, Optional

from dagster import AutoMaterializePolicy, AutoMaterializeRule
from dagster_dbt import KeyPrefixDagsterDbtTranslator
from dagster_dbt.asset_utils import default_group_from_dbt_resource_props


class CustomDagsterDbtTranslator(KeyPrefixDagsterDbtTranslator):
    def get_auto_materialize_policy(
        self, dbt_resource_props: Mapping[str, Any]
    ) -> Optional[AutoMaterializePolicy]:
        auto_materialize_policy_config = (
            dbt_resource_props.get("meta", {})
            .get("dagster", {})
            .get("auto_materialize_policy", {})
        )

        if auto_materialize_policy_config.get("type") == "lazy":
            return AutoMaterializePolicy.lazy()
        else:
            return AutoMaterializePolicy.eager(
                auto_materialize_policy_config.get("max_materializations_per_minute")
            ).without_rules(AutoMaterializeRule.skip_on_parent_outdated())

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
