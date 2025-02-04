from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.coupa.assets import build_coupa_asset

resources = [
    "addresses",
    "business_groups",
    "users",
    # "role",
    # "user_business_group_mapping",
    # "user_role_mapping",
]

assets = [
    build_coupa_asset(code_location=CODE_LOCATION, resource=resource, schema=...)
    for resource in resources
]
