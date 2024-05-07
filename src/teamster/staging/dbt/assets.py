import json
import pathlib

from teamster.core.dbt.assets import build_dbt_assets, build_dbt_external_source_assets
from teamster.core.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

manifest = json.loads(
    s=pathlib.Path("src/dbt/kipptaf/target/manifest.json").read_text()
)

dagster_dbt_translator = CustomDagsterDbtTranslator(
    asset_key_prefix="staging", source_asset_key_prefix="staging"
)

dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    exclude="tag:stage_external_sources",
)

dbt_external_source_assets = build_dbt_external_source_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
)

assets = [
    dbt_assets,
    dbt_external_source_assets,
]
