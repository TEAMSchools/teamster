import json

from teamster.code_locations.kippcamden import CODE_LOCATION, DBT_PROJECT
from teamster.libraries.dbt.assets import build_dbt_assets
from teamster.libraries.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

manifest = json.loads(s=DBT_PROJECT.manifest_path.read_text())

dagster_dbt_translator = CustomDagsterDbtTranslator(code_location=CODE_LOCATION)

dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}_dbt_assets",
)

assets = [
    dbt_assets,
]
