from dagster import config_from_files

from teamster.core.datagun.assets import (
    build_bigquery_extract_sftp_asset,
    build_bigquery_query_sftp_asset,
)
from teamster.kipptaf.adp.payroll.assets import GENERAL_LEDGER_FILE_PARTITIONS_DEF

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/datagun/config"

# BQ extract job
blissbook_extract_assets = [
    build_bigquery_extract_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/blissbook.yaml"])["assets"]
]

clever_extract_assets = [
    build_bigquery_extract_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/clever.yaml"])["assets"]
]

coupa_extract_assets = [
    build_bigquery_extract_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/coupa.yaml"])["assets"]
]

egencia_extract_assets = [
    build_bigquery_extract_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/egencia.yaml"])["assets"]
]

illuminate_extract_assets = [
    build_bigquery_extract_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/illuminate.yaml"])["assets"]
]

littlesis_extract_assets = [
    build_bigquery_extract_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/littlesis.yaml"])["assets"]
]

# BQ query
deanslist_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/deanslist.yaml"])["assets"]
]

idauto_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/idauto.yaml"])["assets"]
]

intacct_extract_asset = build_bigquery_query_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    query_config={
        "type": "schema",
        "value": {
            "table": {
                "name": "rpt_gsheets__intacct_integration_file",
                "schema": "kipptaf_extracts",
            }
        },
    },
    file_config={"stem": "adp_payroll_{date}_{group_code}", "suffix": "csv"},
    destination_config={
        "name": "couchdrop",
        "path": "/data-team/Data Integration/Couchdrop/Accounting/Intacct",
    },
    partitions_def=GENERAL_LEDGER_FILE_PARTITIONS_DEF,
)

_all = [
    *blissbook_extract_assets,
    *clever_extract_assets,
    *coupa_extract_assets,
    *deanslist_extract_assets,
    *egencia_extract_assets,
    *idauto_extract_assets,
    *illuminate_extract_assets,
    *littlesis_extract_assets,
]
