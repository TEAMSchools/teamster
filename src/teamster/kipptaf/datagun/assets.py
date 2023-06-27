from dagster import config_from_files

from teamster.core.datagun.assets import (
    build_bigquery_query_sftp_asset,
    generate_extract_assets,
)

from .. import CODE_LOCATION, LOCAL_TIMEZONE

config_dir = f"src/teamster/{CODE_LOCATION}/datagun/config"

adp_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="adp",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

alchemer_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="alchemer",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

blissbook_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="blissbook",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

clever_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="clever",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

coupa_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="coupa",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

deanslist_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="deanslist",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

egencia_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="egencia",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

fpodms_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="fpodms",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

gam_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="gam",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

idauto_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="idauto",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

illuminate_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="illuminate",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

littlesis_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="littlesis",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

njdoe_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="njdoe",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

razkids_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="razkids",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

read180_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="read180",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

whetstone_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="whetstone",
    extract_type="sftp",
    timezone=LOCAL_TIMEZONE,
)

gsheet_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION,
    name="gsheets",
    extract_type="gsheet",
    timezone=LOCAL_TIMEZONE,
)

bigquery_extract_assets = [
    build_bigquery_query_sftp_asset(
        code_location=CODE_LOCATION,
        timezone=LOCAL_TIMEZONE,
        **a,
    )
    for a in config_from_files([f"{config_dir}/idauto_v2.yaml"])["assets"]
]

__all__ = [
    *adp_extract_assets,
    *alchemer_extract_assets,
    *blissbook_extract_assets,
    *clever_extract_assets,
    *coupa_extract_assets,
    *deanslist_extract_assets,
    *egencia_extract_assets,
    *fpodms_extract_assets,
    *gam_extract_assets,
    *gsheet_extract_assets,
    *idauto_extract_assets,
    *illuminate_extract_assets,
    *littlesis_extract_assets,
    *njdoe_extract_assets,
    *razkids_extract_assets,
    *read180_extract_assets,
    *whetstone_extract_assets,
    *bigquery_extract_assets,
]
