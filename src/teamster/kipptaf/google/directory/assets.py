from dagster import AssetExecutionContext, Output, StaticPartitionsDefinition, asset

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_record_schema,
    get_avro_schema_valid_check_spec,
)

from ... import CODE_LOCATION
from ..resources import GoogleDirectoryResource
from .schema import ASSET_FIELDS

key_prefix = [CODE_LOCATION, "google", "directory"]
asset_kwargs = {
    "io_manager_key": "io_manager_gcs_avro",
    "group_name": "google_directory",
    "compute_kind": "google_directory",
}


@asset(
    key=[*key_prefix, "orgunits"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "orgunits"])],
    **asset_kwargs,  # type: ignore
)
def orgunits(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_orgunits(org_unit_type="all")
    schema = get_avro_record_schema(name="orgunits", fields=ASSET_FIELDS["orgunits"])

    yield Output(value=([data], schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=[data], schema=schema
    )


@asset(
    key=[*key_prefix, "users"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "users"])],
    **asset_kwargs,  # type: ignore
)
def users(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_users(projection="full")
    schema = get_avro_record_schema(name="users", fields=ASSET_FIELDS["users"])

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
    )


@asset(
    key=[*key_prefix, "groups"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "groups"])],
    **asset_kwargs,  # type: ignore
)
def groups(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_groups()
    schema = get_avro_record_schema(name="groups", fields=ASSET_FIELDS["groups"])

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
    )


@asset(
    key=[*key_prefix, "roles"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "roles"])],
    **asset_kwargs,  # type: ignore
)
def roles(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_roles()
    schema = get_avro_record_schema(name="roles", fields=ASSET_FIELDS["roles"])

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
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
    schema = get_avro_record_schema(
        name="role_assignments", fields=ASSET_FIELDS["role_assignments"]
    )

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
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
    schema = get_avro_record_schema(name="members", fields=ASSET_FIELDS["members"])

    yield Output(value=(data, schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=schema
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

_all = [
    groups,
    members,
    orgunits,
    role_assignments,
    roles,
    users,
]
