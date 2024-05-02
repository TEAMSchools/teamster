import json
import pathlib

from dagster import AssetExecutionContext, Output
from dagster_dbt import DbtCliResource

from teamster.core.dbt.assets import build_dbt_assets, dbt_external_source_assets
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
            # "fqn:kipptaf.extracts.google.sheets.rpt_gsheets__intacct_integration_file",
            # "fqn:kipptaf.adp.payroll.staging.stg_adp_payroll__general_ledger_file",
        ]
    ),
)


@dbt_external_source_assets(
    manifest=manifest,
    dagster_dbt_translator=dagster_dbt_translator,
    select="tag:stage_external_sources",
)
def external_source_dbt_assets(context: AssetExecutionContext, dbt_cli: DbtCliResource):
    source_selection = [
        f"{context.assets_def.group_names_by_key[asset_key]}.{asset_key.path[-1]}"
        for asset_key in context.selected_asset_keys
    ]

    # run dbt stage_external_sources
    dbt_run_operation = dbt_cli.cli(
        args=[
            "run-operation",
            "stage_external_sources",
            "--args",
            json.dumps({"select": " ".join(source_selection)}),
            "--vars",
            json.dumps({"ext_full_refresh": True}),
        ],
        manifest=manifest,
        dagster_dbt_translator=dagster_dbt_translator,
    )

    for event in dbt_run_operation.stream_raw_events():
        context.log.info(event)

    for output_name in context.selected_output_names:
        yield Output(value=None, output_name=output_name)


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

# external_source_dbt_assets = build_dbt_external_source_assets(
#     code_location=CODE_LOCATION,
#     manifest=manifest,
#     dagster_dbt_translator=dagster_dbt_translator,
# )

assets = [
    dbt_assets,
    # adp_payroll_dbt_assets,
    external_source_dbt_assets,
]
