import json
import pathlib

from dagster import AssetExecutionContext, materialize
from dagster_dbt import DbtCliResource, dbt_assets

from teamster.core.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator
from teamster.core.resources import get_dbt_cli_resource

MANIFEST = json.loads(
    s=pathlib.Path("src/dbt/kipptaf/target/manifest.json").read_text()
)

dagster_dbt_translator = CustomDagsterDbtTranslator(
    asset_key_prefix="staging", source_asset_key_prefix="staging"
)


@dbt_assets(
    manifest=MANIFEST,
    exclude="tag:stage_external_sources",
    dagster_dbt_translator=dagster_dbt_translator,
)
def _dbt_assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
    latest_code_versions = context.instance.get_latest_materialization_code_versions(
        asset_keys=context.selected_asset_keys
    )

    new_code_version_asset_keys = [
        asset_key
        for asset_key, current_code_version in context.assets_def.code_versions_by_key.items()
        if current_code_version != latest_code_versions.get(asset_key)
    ]

    for asset_key in context.selected_asset_keys:
        context.log.info(asset_key)
        # if manifest node config.materialized is not view (keep)
        # if view:
        #   if asset key is updated (keep)
        #   if any upstream asset keys have updated (keep)
        # else yield materialization

    dbt_parse = dbt_cli.cli(args=["compile"], context=context)
    yield from dbt_parse.stream()


def test_dbt_assets():
    result = materialize(
        assets=[_dbt_assets], resources={"dbt_cli": get_dbt_cli_resource("staging")}
    )

    assert result.success
