import json
import pathlib

from teamster.core.dbt.assets import build_dbt_assets, build_dbt_external_source_assets
from teamster.core.dbt.dagster_dbt_translator import CustomDagsterDbtTranslator
from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.adp.payroll.assets import GENERAL_LEDGER_FILE_PARTITIONS_DEF

manifest = json.loads(
    s=pathlib.Path(f"src/dbt/{CODE_LOCATION}/target/manifest.json").read_text()
)

dagster_dbt_translator = CustomDagsterDbtTranslator(
    asset_key_prefix=CODE_LOCATION, source_asset_key_prefix=CODE_LOCATION
)

dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}_dbt_assets",
    exclude="tag:stage_external_sources source:adp_payroll+",
)

adp_payroll_dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}_adp_payroll_dbt_assets",
    partitions_def=GENERAL_LEDGER_FILE_PARTITIONS_DEF,
    select="stg_adp_payroll__general_ledger_file+",
)

external_source_dbt_assets = build_dbt_external_source_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}_external_source_dbt_assets",
    select="tag:stage_external_sources",
    exclude="source:adp_payroll",
)

adp_payroll_external_source_dbt_assets = build_dbt_external_source_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    name=f"{CODE_LOCATION}_adp_payroll_external_source_dbt_assets",
    partitions_def=GENERAL_LEDGER_FILE_PARTITIONS_DEF,
    select="source:adp_payroll",
)

assets = [
    adp_payroll_dbt_assets,
    adp_payroll_external_source_dbt_assets,
    dbt_assets,
    external_source_dbt_assets,
]
