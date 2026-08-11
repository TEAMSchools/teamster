from collections.abc import Mapping
from typing import Any

from dagster import AssetKey, AutomationCondition
from dagster_dbt import DagsterDbtTranslator, DagsterDbtTranslatorSettings

from teamster.core.automation_conditions import (
    dbt_cron_automation_condition,
    dbt_table_automation_condition,
    dbt_union_relations_automation_condition,
    dbt_view_automation_condition,
)


def _get_dbt_meta(dbt_resource_props: Mapping[str, Any]) -> Mapping[str, Any]:
    """Resolve a node's meta dict: config.meta wins, top-level meta is the
    fallback.

    NOTE: this is an or-short-circuit on the WHOLE dict, not a per-key merge —
    a model setting any config.meta key hides ALL top-level meta keys (e.g. a
    top-level meta.dagster.asset_key would be dropped if config.meta carries
    only an automation_condition). Set every dagster key on the same side.
    """
    return dbt_resource_props.get("config", {}).get(
        "meta", {}
    ) or dbt_resource_props.get("meta", {})


class CustomDagsterDbtTranslator(DagsterDbtTranslator):
    def __init__(
        self,
        code_location: str,
        local_timezone: str | None = None,
        settings: DagsterDbtTranslatorSettings | None = None,
    ) -> None:
        self.code_location = code_location
        self.local_timezone = local_timezone

        super().__init__(settings)

    def get_tags(self, dbt_resource_props: Mapping[str, Any]) -> Mapping[str, str]:
        tags = super().get_tags(dbt_resource_props)
        materialized = dbt_resource_props.get("config", {}).get("materialized", "view")
        return {**tags, "dagster/materialized": materialized}

    def get_asset_key(self, dbt_resource_props: Mapping[str, Any]) -> AssetKey:
        asset_key = super().get_asset_key(dbt_resource_props)

        dbt_meta = _get_dbt_meta(dbt_resource_props)

        if dbt_meta.get("dagster", {}).get("asset_key", []):
            return asset_key

        return asset_key.with_prefix(self.code_location)

    def get_automation_condition(
        self, dbt_resource_props: Mapping[str, Any]
    ) -> AutomationCondition | None:
        materialized = dbt_resource_props.get("config", {}).get("materialized", "view")

        # per-model override: meta.dagster.automation_condition.cron_schedule
        # puts an expensive table on a cron cadence instead of the eager
        # (rebuild-on-any-upstream-update) table condition. Tables only —
        # views/ephemerals keep their view or union_relations condition
        # (a union_relations view losing ancestor code-version detection
        # goes stale non-self-healingly; see core/CLAUDE.md)
        if materialized not in ("view", "ephemeral"):
            condition_meta = (
                _get_dbt_meta(dbt_resource_props)
                .get("dagster", {})
                .get("automation_condition", {})
            )
            cron_schedule = condition_meta.get("cron_schedule")

            if cron_schedule:
                return dbt_cron_automation_condition(
                    cron_schedule=cron_schedule,
                    cron_timezone=condition_meta.get("cron_timezone")
                    or self.local_timezone,
                )

        # union_relations views need dep-aware refresh: their compiled SQL
        # resolves columns at run time via the macro and becomes stale when
        # upstream tables are re-materialized with schema changes
        if materialized == "view" and "union_relations" in dbt_resource_props.get(
            "raw_code", ""
        ):
            return dbt_union_relations_automation_condition()

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
