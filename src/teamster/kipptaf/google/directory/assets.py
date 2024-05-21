from dagster import AssetExecutionContext, Output, StaticPartitionsDefinition, asset

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)
from teamster.google.directory.resources import GoogleDirectoryResource
from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.google.directory.schema import (
    GROUPS_SCHEMA,
    MEMBERS_SCHEMA,
    ORGUNITS_SCHEMA,
    ROLE_ASSIGNMENTS_SCHEMA,
    ROLES_SCHEMA,
    USERS_SCHEMA,
)

key_prefix = [CODE_LOCATION, "google", "directory"]
asset_kwargs = {
    "io_manager_key": "io_manager_gcs_avro",
    "group_name": "google_directory",
    "compute_kind": "python",
}


@asset(
    key=[*key_prefix, "orgunits"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "orgunits"])],
    **asset_kwargs,  # type: ignore
)
def orgunits(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_orgunits(org_unit_type="all")

    yield Output(value=([data], ORGUNITS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=[data], schema=ORGUNITS_SCHEMA
    )


@asset(
    key=[*key_prefix, "users"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "users"])],
    **asset_kwargs,  # type: ignore
)
def users(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_users(projection="full")

    yield Output(value=(data, USERS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=USERS_SCHEMA
    )


@asset(
    key=[*key_prefix, "groups"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "groups"])],
    **asset_kwargs,  # type: ignore
)
def groups(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_groups()

    yield Output(value=(data, GROUPS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=GROUPS_SCHEMA
    )


@asset(
    key=[*key_prefix, "roles"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "roles"])],
    **asset_kwargs,  # type: ignore
)
def roles(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_roles()

    yield Output(value=(data, ROLES_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=ROLES_SCHEMA
    )


@asset(
    key=[*key_prefix, "role_assignments"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "role_assignments"])],
    **asset_kwargs,  # type: ignore
)
def role_assignments(
    context: AssetExecutionContext, google_directory: GoogleDirectoryResource
):
    data = google_directory.list_role_assignments()

    yield Output(
        value=(data, ROLE_ASSIGNMENTS_SCHEMA), metadata={"record_count": len(data)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=ROLE_ASSIGNMENTS_SCHEMA
    )


@asset(
    key=[*key_prefix, "members"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "members"])],
    partitions_def=StaticPartitionsDefinition(
        [
            "group-students-camden@teamstudents.org",
            "group-students-miami@teamstudents.org",
            "group-students-newark@teamstudents.org",
        ]
    ),
    **asset_kwargs,  # type: ignore
)
def members(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_members(group_key=context.partition_key)

    yield Output(value=(data, MEMBERS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=MEMBERS_SCHEMA
    )


google_directory_nonpartitioned_assets = [
    groups,
    orgunits,
    role_assignments,
    roles,
    users,
]

google_directory_partitioned_assets = [
    members,
]

assets = [
    groups,
    members,
    orgunits,
    role_assignments,
    roles,
    users,
]
