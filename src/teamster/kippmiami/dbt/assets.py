from teamster.core.dbt.assets import build_dbt_assets, build_dbt_external_source_assets
from teamster.core.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

from .. import CODE_LOCATION
from .manifest import dbt_manifest

dagster_dbt_translator = CustomDagsterDbtTranslator(
    asset_key_prefix=CODE_LOCATION, source_asset_key_prefix=CODE_LOCATION
)

dbt_assets = build_dbt_assets(
    dbt_manifest=dbt_manifest, dagster_dbt_translator=dagster_dbt_translator
)

dbt_external_source_assets = build_dbt_external_source_assets(
    code_location=CODE_LOCATION,
    manifest=dbt_manifest,
    dagster_dbt_translator=dagster_dbt_translator,
)

_all = [
    dbt_assets,
    dbt_external_source_assets,
]
