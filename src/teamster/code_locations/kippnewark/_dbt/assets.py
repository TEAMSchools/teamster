import json

from dagster_dbt import DbtProject

from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.libraries.dbt.assets import (
    build_dbt_assets,
    build_dbt_external_source_assets,
)
from teamster.libraries.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

dbt_project = DbtProject(project_dir=f"src/dbt/{CODE_LOCATION}")

manifest = json.loads(s=dbt_project.manifest_path.read_text())

dagster_dbt_translator = CustomDagsterDbtTranslator(code_location=CODE_LOCATION)

dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    exclude="tag:stage_external_sources",
    name=f"{CODE_LOCATION}_dbt_assets",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "1750m"}, "limits": {"cpu": "1750m"}}
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
