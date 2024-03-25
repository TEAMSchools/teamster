import json

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets


def build_dbt_assets(dbt_manifest, dagster_dbt_translator):
    @dbt_assets(
        manifest=dbt_manifest,
        exclude="tag:stage_external_sources",
        dagster_dbt_translator=dagster_dbt_translator,
    )
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
        dbt_build = dbt_cli.cli(args=["build"], context=context)

        yield from dbt_build.stream()

    return _assets


def build_dbt_external_source_assets(manifest, dagster_dbt_translator):
    @dbt_assets(
        manifest=manifest,
        select="tag:stage_external_sources",
        dagster_dbt_translator=dagster_dbt_translator,
    )
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
        source_selection = [
            f"{context.assets_def.group_names_by_key[asset_key]}.{asset_key.path[-1]}"
            for asset_key in context.selected_asset_keys
        ]

        dbt_run_operation = dbt_cli.cli(
            args=[
                "run-operation",
                "stage_external_sources",
                "--args",
                json.dumps({"select": " ".join(source_selection)}),
                "--vars",
                json.dumps({"ext_full_refresh": True}),
            ],
            manifest=manifest,
            dagster_dbt_translator=dagster_dbt_translator,
        )

        yield from dbt_run_operation.stream()

    return _assets
