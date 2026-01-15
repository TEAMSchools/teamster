import json

from dagster import AssetSpec
from dagster_dbt import get_asset_key_for_model

from teamster.code_locations.kipptaf import CODE_LOCATION, DBT_PROJECT
from teamster.code_locations.kipptaf.adp.payroll.assets import (
    GENERAL_LEDGER_FILE_PARTITIONS_DEF,
)
from teamster.libraries.dbt.assets import build_dbt_assets
from teamster.libraries.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator

manifest = json.loads(s=DBT_PROJECT.manifest_path.read_text())

dagster_dbt_translator = CustomDagsterDbtTranslator(code_location=CODE_LOCATION)

all_dbt_assets = build_dbt_assets(
    manifest=manifest, dagster_dbt_translator=dagster_dbt_translator
)

core_dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}__dbt_assets",
    exclude="source:adp_payroll+ tag:google_sheet extracts",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "500m"}, "limits": {"cpu": "1500m"}}
            }
        }
    },
)

reporting_dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}__dbt_assets__reporting",
    select="extracts",
    exclude="source:adp_payroll+",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "500m"}, "limits": {"cpu": "1750m"}}
            }
        }
    },
)

google_sheet_dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}__dbt_assets__google_sheets",
    select="tag:google_sheet",
    op_tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"requests": {"cpu": "500m"}, "limits": {"cpu": "1500m"}}
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
                "resources": {"requests": {"cpu": "500m"}, "limits": {"cpu": "1250m"}}
            }
        }
    },
)

asset_specs = [
    AssetSpec(
        key=[CODE_LOCATION, "dbt", "exposures", exposure["label"]],
        deps=[
            get_asset_key_for_model(dbt_assets=[all_dbt_assets], model_name=ref["name"])
            for ref in exposure["refs"]
        ],
        metadata={"url": exposure.get("url")},
        kinds=set(exposure["config"]["meta"]["dagster"]["kinds"]),
    )
    for exposure in manifest["exposures"].values()
    if "tableau" not in exposure["config"]["meta"]["dagster"]["kinds"]
]

assets = [
    adp_payroll_dbt_assets,
    core_dbt_assets,
    google_sheet_dbt_assets,
    reporting_dbt_assets,
]
