from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.coupa.schema import ADDRESS_SCHEMA, USER_SCHEMA
from teamster.libraries.coupa.assets import build_coupa_asset

addresses = build_coupa_asset(
    code_location=CODE_LOCATION, resource="addresses", schema=ADDRESS_SCHEMA
)

users = build_coupa_asset(
    code_location=CODE_LOCATION, resource="users", schema=USER_SCHEMA
)

assets = [
    addresses,
    users,
]
