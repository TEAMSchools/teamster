import json
import pathlib

from dagster import (
    AssetExecutionContext,
    AssetMaterialization,
    AssetsDefinition,
    materialize,
)
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

from teamster.core.resources import get_dbt_cli_resource
from teamster.libraries.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

MANIFEST = json.loads(
    s=pathlib.Path("src/dbt/kipptaf/target/manifest.json").read_text()
)

MANIFEST_NODES = MANIFEST["nodes"]

DAGSTER_DBT_TRANSLATOR = CustomDagsterDbtTranslator(code_location="kipptaf")


@dbt_assets(
    manifest=MANIFEST,
    exclude="tag:stage_external_sources",
    dagster_dbt_translator=DAGSTER_DBT_TRANSLATOR,
)
def _dbt_assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
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

    for output_name in context.op_execution_context.selected_output_names:
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
            # trunk-ignore(pyright/reportAttributeAccessIssue)
            context.selected_asset_keys.remove(node_asset_key)

    if context.selected_asset_keys:
        dbt_parse = dbt_cli.cli(args=["compile"], context=context)

        yield from dbt_parse.stream()
    else:
        for asset_key in asset_materialization_keys:
            yield AssetMaterialization(asset_key=asset_key)


def _test_dbt_assets(
    assets: list[AssetsDefinition], code_location: str, selection: list[str]
):
    result = materialize(
        assets=assets,
        resources={
            "dbt_cli": get_dbt_cli_resource(
                dbt_project=DbtProject(project_dir=f"src/dbt/{code_location}"),
                test=True,
            )
        },
        selection=selection,
    )

    assert result.success


def test_dbt_assets():
    _test_dbt_assets(
        assets=[_dbt_assets],
        code_location="kipptaf",
        selection=["kipptaf/tableau/rpt_tableau__assessment_dashboard"],
    )


def test_dbt_assets_kipptaf():
    from teamster.code_locations.kipptaf._dbt.assets import dbt_assets

    _test_dbt_assets(
        assets=[dbt_assets],
        code_location="kipptaf",
        selection=[
            "kipptaf/schoolmint_grow/stg_schoolmint_grow__users",
            "kipptaf/schoolmint_grow/stg_schoolmint_grow__schools",
            "kipptaf/schoolmint_grow/int_schoolmint_grow__observations",
            "kipptaf/illuminate/stg_illuminate__reporting_groups",
        ],
    )
