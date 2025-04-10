import pathlib

from dagster import config_from_files

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.payroll.assets import (
    GENERAL_LEDGER_FILE_PARTITIONS_DEF,
)
from teamster.libraries.extracts.assets import build_bigquery_query_sftp_asset

config_dir = pathlib.Path(__file__).parent / "config"

clever_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION,
        timezone=LOCAL_TIMEZONE,
        destination_config={"name": "clever"},
        **a,
    )
    for a in config_from_files([f"{config_dir}/clever.yaml"])["assets"]
]

coupa_extract = build_bigquery_query_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    query_config={
        "type": "schema",
        "value": {
            "table": {
                "name": "rpt_coupa__users",
                "schema": "kipptaf_extracts",
            }
        },
    },
    file_config={"stem": "users_{today}", "suffix": "csv"},
    destination_config={"name": "coupa", "path": "/Incoming/Users"},
)

deanslist_annual_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION,
        timezone=LOCAL_TIMEZONE,
        destination_config={"name": "deanslist"},
        **a,
    )
    for a in config_from_files([f"{config_dir}/deanslist-annual.yaml"])["assets"]
]

deanslist_continuous_extract = build_bigquery_query_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    query_config={
        "type": "schema",
        "value": {
            "table": {
                "name": "rpt_deanslist__student_misc",
                "schema": "kipptaf_extracts",
            }
        },
    },
    file_config={"stem": "deanslist_student_misc", "suffix": "json.gz"},
    destination_config={"name": "deanslist"},
)

egencia_extract = build_bigquery_query_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    query_config={
        "type": "schema",
        "value": {
            "table": {
                "name": "rpt_egencia__users",
                "schema": "kipptaf_extracts",
            }
        },
    },
    file_config={"stem": "users_{today}", "suffix": "csv"},
    destination_config={"name": "egencia", "path": "/global/50323/USERS"},
)

idauto_extract = build_bigquery_query_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    query_config={
        "type": "schema",
        "value": {
            "table": {"name": "rpt_idauto__staff_roster", "schema": "kipptaf_extracts"}
        },
    },
    file_config={
        "stem": "AD",
        "suffix": "csv",
        "encoding": "latin1",
        "format": {"quoting": 1},
    },
    destination_config={"name": "idauto"},
)

illuminate_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION,
        timezone=LOCAL_TIMEZONE,
        destination_config={"name": "illuminate"},
        **a,
    )
    for a in config_from_files([f"{config_dir}/illuminate.yaml"])["assets"]
]

intacct_extract = build_bigquery_query_sftp_asset(
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
    destination_config={"name": "couchdrop", "path": "/data-team/accounting/intacct"},
    partitions_def=GENERAL_LEDGER_FILE_PARTITIONS_DEF,
)

littlesis_extract = build_bigquery_query_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    query_config={
        "type": "schema",
        "value": {
            "table": {
                "name": "rpt_littlesis__enrollments",
                "schema": "kipptaf_extracts",
            }
        },
    },
    file_config={"stem": "littlesis_extract", "suffix": "csv"},
    destination_config={"name": "littlesis"},
)

assets = [
    coupa_extract,
    deanslist_continuous_extract,
    egencia_extract,
    idauto_extract,
    intacct_extract,
    littlesis_extract,
    *clever_extract_assets,
    *deanslist_annual_extract_assets,
    *illuminate_extract_assets,
]
