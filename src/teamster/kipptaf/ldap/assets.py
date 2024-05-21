from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.ldap.schema import GROUP_SCHEMA, USER_PERSON_SCHEMA
from teamster.ldap.assets import build_ldap_asset

user_person = build_ldap_asset(
    asset_key=[CODE_LOCATION, "ldap", "user_person"],
    search_base="dc=teamschools,dc=kipp,dc=org",
    search_filter="(&(objectClass=user)(objectCategory=person))",
    schema=USER_PERSON_SCHEMA,
    op_tags={
        "dagster-k8s/config": {
            "container_config": {"resources": {"requests": {"memory": "1.0Gi"}}}
        }
    },
)

user_person = build_ldap_asset(
    asset_key=[CODE_LOCATION, "ldap", "group"],
    search_base="dc=teamschools,dc=kipp,dc=org",
    search_filter="(objectClass=group)",
    schema=GROUP_SCHEMA,
)

assets = [
    user_person,
    user_person,
]
