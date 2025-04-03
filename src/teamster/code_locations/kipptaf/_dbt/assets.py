import json

from teamster.code_locations.kipptaf import CODE_LOCATION, DBT_PROJECT
from teamster.code_locations.kipptaf.adp.payroll.assets import (
    GENERAL_LEDGER_FILE_PARTITIONS_DEF,
)
from teamster.libraries.dbt.assets import build_dbt_assets
from teamster.libraries.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

manifest = json.loads(s=DBT_PROJECT.manifest_path.read_text())

dagster_dbt_translator = CustomDagsterDbtTranslator(code_location=CODE_LOCATION)

dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}__dbt_assets",
    exclude="source:adp_payroll+ tag:google_sheet",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "250m"}, "limits": {"cpu": "1750m"}}
            }
        }
    },
)

google_sheet_dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}__dbt_assets__google_sheets",
    select="tag:google_sheet",
    exclude="source:adp_payroll+",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "250m"}, "limits": {"cpu": "1250m"}}
            }
        }
    },
)

adp_payroll_dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}__dbt_assets__adp_payroll",
    partitions_def=GENERAL_LEDGER_FILE_PARTITIONS_DEF,
    select="source:adp_payroll+",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "250m"}, "limits": {"cpu": "1250m"}}
            }
        }
    },
)

assets = [
    adp_payroll_dbt_assets,
    dbt_assets,
    google_sheet_dbt_assets,
]
