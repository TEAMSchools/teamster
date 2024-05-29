import json

from dagster import AssetExecutionContext, Output
from dagster_dbt import DbtCliResource, dbt_assets

from teamster.core.dbt.asset_decorator import dbt_external_source_assets


def build_dbt_assets(
    manifest,
    dagster_dbt_translator,
    select="fqn:*",
    exclude=None,
    partitions_def=None,
    name=None,
    op_tags=None,
):
    @dbt_assets(
        manifest=manifest,
        select=select,
        exclude=exclude,
        name=name,
        partitions_def=partitions_def,
        dagster_dbt_translator=dagster_dbt_translator,
        op_tags=op_tags,
    )
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
        dbt_build = dbt_cli.cli(args=["build"], context=context)

        yield from dbt_build.stream()

    return _assets


def build_dbt_external_source_assets(
    manifest,
    dagster_dbt_translator,
    select="fqn:*",
    exclude=None,
    partitions_def=None,
    name=None,
    op_tags=None,
):
    @dbt_external_source_assets(
        manifest=manifest,
        select=select,
        exclude=exclude,
        name=name,
        partitions_def=partitions_def,
        dagster_dbt_translator=dagster_dbt_translator,
        op_tags=op_tags,
    )
    def _assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
        source_selection = [
            f"{context.assets_def.group_names_by_key[asset_key]}.{asset_key.path[-1]}"
            for asset_key in context.selected_asset_keys
        ]

        # run dbt stage_external_sources
        dbt_cli.cli(
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

        for output_name in context.selected_output_names:
            yield Output(value=None, output_name=output_name)

    return _assets
