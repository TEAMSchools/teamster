from teamster.core.datagun.assets import generate_extract_assets

from .. import CODE_LOCATION

adp_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="adp", extract_type="sftp"
)

alchemer_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="alchemer", extract_type="sftp"
)

blissbook_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="blissbook", extract_type="sftp"
)

clever_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="clever", extract_type="sftp"
)

coupa_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="coupa", extract_type="sftp"
)

deanslist_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="deanslist", extract_type="sftp"
)

egencia_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="egencia", extract_type="sftp"
)

fpodms_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="fpodms", extract_type="sftp"
)

gam_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="gam", extract_type="sftp"
)

idauto_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="idauto", extract_type="sftp"
)

illuminate_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="illuminate", extract_type="sftp"
)

littlesis_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="littlesis", extract_type="sftp"
)

njdoe_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="njdoe", extract_type="sftp"
)

razkids_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="razkids", extract_type="sftp"
)

read180_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="read180", extract_type="sftp"
)

whetstone_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="whetstone", extract_type="sftp"
)

gsheet_extract_assets = generate_extract_assets(
    code_location=CODE_LOCATION, name="gsheets", extract_type="gsheet"
)

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
]
