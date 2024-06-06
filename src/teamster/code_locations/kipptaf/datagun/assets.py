import pathlib

from dagster import AutoMaterializePolicy, config_from_files

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.payroll.assets import (
    GENERAL_LEDGER_FILE_PARTITIONS_DEF,
)
from teamster.libraries.datagun.assets import (
    build_bigquery_extract_sftp_asset,
    build_bigquery_query_sftp_asset,
)

config_dir = pathlib.Path(__file__).parent / "config"

# BQ extract job
blissbook_extract = build_bigquery_extract_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    dataset_config={
        "dataset_id": "kipptaf_extracts",
        "table_id": "rpt_blissbook__employee_list",
    },
    file_config={"stem": "members", "suffix": "csv"},
    destination_config={"name": "blissbook"},
)

clever_extract_assets = [
    build_bigquery_extract_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/clever.yaml"])["assets"]
]

coupa_extract = build_bigquery_extract_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    dataset_config={"dataset_id": "kipptaf_extracts", "table_id": "rpt_coupa__users"},
    file_config={"stem": "users_{today}", "suffix": "csv"},
    destination_config={"name": "coupa", "path": "/Incoming/Users"},
)

egencia_extract = build_bigquery_extract_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    dataset_config={"dataset_id": "kipptaf_extracts", "table_id": "rpt_egencia__users"},
    file_config={"stem": "users_{today}", "suffix": "csv"},
    destination_config={"name": "egencia", "path": "/global/50323/USERS"},
)

illuminate_extract_assets = [
    build_bigquery_extract_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/illuminate.yaml"])["assets"]
]

littlesis_extract = build_bigquery_extract_sftp_asset(
    code_location=CODE_LOCATION,
    timezone=LOCAL_TIMEZONE,
    dataset_config={
        "dataset_id": "kipptaf_extracts",
        "table_id": "rpt_littlesis__enrollments",
    },
    file_config={"stem": "littlesis_extract", "suffix": "csv"},
    destination_config={"name": "littlesis"},
)

# BQ query
deanslist_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION, timezone=LOCAL_TIMEZONE, **a
    )
    for a in config_from_files([f"{config_dir}/deanslist.yaml"])["assets"]
]

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
    auto_materialize_policy=AutoMaterializePolicy.eager(
        max_materializations_per_minute=4
    ),
)

assets = [
    blissbook_extract,
    coupa_extract,
    egencia_extract,
    idauto_extract,
    littlesis_extract,
    intacct_extract,
    *clever_extract_assets,
    *deanslist_extract_assets,
    *illuminate_extract_assets,
]
