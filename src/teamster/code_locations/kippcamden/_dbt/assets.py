import json
import pathlib

from teamster.code_locations.kippcamden import CODE_LOCATION
from teamster.libraries.dbt.assets import (
    build_dbt_assets,
    build_dbt_external_source_assets,
)
from teamster.libraries.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

manifest = json.loads(
    s=pathlib.Path(f"src/dbt/{CODE_LOCATION}/target/manifest.json").read_text()
)

dagster_dbt_translator = CustomDagsterDbtTranslator(
    asset_key_prefix=CODE_LOCATION, source_asset_key_prefix=CODE_LOCATION
)

dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    exclude="tag:stage_external_sources",
    name=f"{CODE_LOCATION}_dbt_assets",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "1500m"}, "limits": {"cpu": "1500m"}}
            }
        }
    },
)

external_source_dbt_assets = build_dbt_external_source_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    select="tag:stage_external_sources",
    name=f"{CODE_LOCATION}_external_source_dbt_assets",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "750m"}, "limits": {"cpu": "750m"}}
            }
        }
    },
)

assets = [
    dbt_assets,
    external_source_dbt_assets,
]
