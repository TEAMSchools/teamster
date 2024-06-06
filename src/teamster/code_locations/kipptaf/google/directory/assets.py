from dagster import AssetExecutionContext, Output, StaticPartitionsDefinition, asset

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.google.directory.schema import (
    GROUPS_SCHEMA,
    MEMBERS_SCHEMA,
    ORGUNITS_SCHEMA,
    ROLE_ASSIGNMENTS_SCHEMA,
    ROLES_SCHEMA,
    USERS_SCHEMA,
)
from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.google.directory.resources import GoogleDirectoryResource

key_prefix = [CODE_LOCATION, "google", "directory"]


@asset(
    key=[*key_prefix, "orgunits"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "orgunits"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    compute_kind="python",
)
def orgunits(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_orgunits(org_unit_type="all")

    yield Output(value=([data], ORGUNITS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=[data], schema=ORGUNITS_SCHEMA
    )


@asset(
    key=[*key_prefix, "users"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "users"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    compute_kind="python",
)
def users(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_users(projection="full")

    yield Output(value=(data, USERS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=USERS_SCHEMA
    )


@asset(
    key=[*key_prefix, "groups"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "groups"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    compute_kind="python",
)
def groups(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_groups()

    yield Output(value=(data, GROUPS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=GROUPS_SCHEMA
    )


@asset(
    key=[*key_prefix, "roles"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "roles"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    compute_kind="python",
)
def roles(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_roles()

    yield Output(value=(data, ROLES_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=ROLES_SCHEMA
    )


@asset(
    key=[*key_prefix, "role_assignments"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "role_assignments"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    compute_kind="python",
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
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "members"])],
    partitions_def=StaticPartitionsDefinition(
        [
            "group-students-camden@teamstudents.org",
            "group-students-miami@teamstudents.org",
            "group-students-newark@teamstudents.org",
        ]
    ),
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    compute_kind="python",
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
