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
    exclude=" ".join(
        [
            "tag:stage_external_sources",
            "fqn:kipptaf.extracts.google.sheets.rpt_gsheets__intacct_integration_file",
            "fqn:kipptaf.adp.payroll.staging.stg_adp_payroll__general_ledger_file",
        ]
    ),
)

adp_payroll_dbt_assets = build_dbt_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    partitions_def=GENERAL_LEDGER_FILE_PARTITIONS_DEF,
    select=" ".join(
        [
            "fqn:kipptaf.extracts.google.sheets.rpt_gsheets__intacct_integration_file",
            "fqn:kipptaf.adp.payroll.staging.stg_adp_payroll__general_ledger_file",
        ]
    ),
)

external_source_dbt_assets = build_dbt_external_source_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    select="tag:stage_external_sources",
)

assets = [
    dbt_assets,
    # adp_payroll_dbt_assets,
    external_source_dbt_assets,
]
