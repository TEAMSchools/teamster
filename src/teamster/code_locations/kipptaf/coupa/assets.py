from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.coupa.schema import (
    ADDRESS_SCHEMA,
    BUSINESS_GROUP_SCHEMA,
    USER_SCHEMA,
)
from teamster.libraries.coupa.assets import build_coupa_asset

resources = [
    ("addresses", ADDRESS_SCHEMA),
    ("business_groups", BUSINESS_GROUP_SCHEMA),
    ("users", USER_SCHEMA),
    # "role",
    # "user_business_group_mapping",
    # "user_role_mapping",
]

assets = [
    build_coupa_asset(code_location=CODE_LOCATION, resource=resource, schema=schema)
    for resource, schema in resources
]
