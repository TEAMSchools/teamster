import json
import pathlib

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from teamster.core.dbt.assets import (
    CustomDagsterDbtTranslator,
    build_dbt_external_source_assets,
)

from .. import CODE_LOCATION

dbt_manifest = json.loads(
    s=pathlib.Path(f"src/dbt/{CODE_LOCATION}/target/manifest.json").read_text()
)

dagster_dbt_translator = CustomDagsterDbtTranslator(
    asset_key_prefix=CODE_LOCATION, source_asset_key_prefix=CODE_LOCATION
)


@dbt_assets(
    manifest=dbt_manifest,
    exclude="tag:stage_external_sources",
    dagster_dbt_translator=dagster_dbt_translator,
)
def _dbt_assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
    dbt_build = dbt_cli.cli(args=["build"], context=context)

    yield from dbt_build.stream()


dbt_external_source_assets = build_dbt_external_source_assets(
    code_location=CODE_LOCATION,
    manifest=dbt_manifest,
    dagster_dbt_translator=dagster_dbt_translator,
)

__all__ = [
    _dbt_assets,
    dbt_external_source_assets,
]
