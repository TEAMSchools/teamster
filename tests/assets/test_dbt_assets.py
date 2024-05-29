import json
import pathlib

from dagster import AssetExecutionContext, AssetMaterialization, materialize
from dagster_dbt import DbtCliResource, dbt_assets

from teamster.core.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator
from teamster.core.resources import get_dbt_cli_resource

MANIFEST = json.loads(
    s=pathlib.Path("src/dbt/kipptaf/target/manifest.json").read_text()
)

MANIFEST_NODES = MANIFEST["nodes"]

DAGSTER_DBT_TRANSLATOR = CustomDagsterDbtTranslator(
    asset_key_prefix="kipptaf", source_asset_key_prefix="kipptaf"
)


@dbt_assets(
    manifest=MANIFEST,
    exclude="tag:stage_external_sources",
    dagster_dbt_translator=DAGSTER_DBT_TRANSLATOR,
)
def _test_dbt_assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
    asset_materialization_keys = []

    latest_code_versions = context.instance.get_latest_materialization_code_versions(
        asset_keys=list(context.selected_asset_keys)
    )

    new_code_version_asset_keys = [
        asset_key
        for asset_key, current_code_version in context.assets_def.code_versions_by_key.items()
        if current_code_version != latest_code_versions.get(asset_key)
    ]

    new_code_version_node_names = set()
    for a in new_code_version_asset_keys:
        new_code_version_node_names.add(f"model.{a.path[0]}.{a.path[-1]}")

    for output_name in context.selected_output_names:
        node = [
            v for k, v in MANIFEST_NODES.items() if k.replace(".", "_") == output_name
        ][0]

        node_asset_key = DAGSTER_DBT_TRANSLATOR.get_asset_key(node)

        if node["config"]["materialized"] != "view":
            pass
        elif node_asset_key in new_code_version_asset_keys:
            pass
        elif set(node["depends_on"]["nodes"]) in new_code_version_node_names:
            pass
        else:
            context.selected_asset_keys.remove(node_asset_key)  # pyright: ignore[reportAttributeAccessIssue]

    if context.selected_asset_keys:
        dbt_parse = dbt_cli.cli(args=["compile"], context=context)

        yield from dbt_parse.stream()
    else:
        for asset_key in asset_materialization_keys:
            yield AssetMaterialization(asset_key=asset_key)


def test_dbt_assets():
    result = materialize(
        assets=[_test_dbt_assets],
        resources={"dbt_cli": get_dbt_cli_resource("kipptaf")},
        selection=["kipptaf/tableau/rpt_tableau__assessment_dashboard"],
    )

    assert result.success


def test_external_source_dbt_assets():
    from teamster.kipptaf.dbt.assets import external_source_dbt_assets

    result = materialize(
        assets=[external_source_dbt_assets],
        resources={"dbt_cli": get_dbt_cli_resource("kipptaf")},
        selection=["kipptaf/google_forms/src_google_forms__responses"],
    )

    assert result.success
