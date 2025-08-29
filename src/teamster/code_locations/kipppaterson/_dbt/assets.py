import json

from teamster.code_locations.kipppaterson import CODE_LOCATION, DBT_PROJECT
from teamster.libraries.dbt.assets import build_dbt_assets
from teamster.libraries.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

manifest = json.loads(s=DBT_PROJECT.manifest_path.read_text())

dagster_dbt_translator = CustomDagsterDbtTranslator(code_location=CODE_LOCATION)

dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}_dbt_assets",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "250m"}, "limits": {"cpu": "1000m"}}
            }
        }
    },
)

assets = [
    dbt_assets,
]
