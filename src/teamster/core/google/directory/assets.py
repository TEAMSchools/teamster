from dagster import AssetExecutionContext, Output, asset

from teamster.core.google.directory.resources import GoogleDirectoryResource
from teamster.core.google.directory.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_google_directory_assets(code_location):
    @asset(
        key=[code_location, "google", "directory", "orgunits"],
        io_manager_key="io_manager_gcs_avro",
    )
    def orgunits(
        context: AssetExecutionContext, google_directory: GoogleDirectoryResource
    ):
        data = google_directory.list_orgunits(org_unit_type="all")
        schema = get_avro_record_schema(
            name="orgunits", fields=ASSET_FIELDS["orgunits"]
        )

        yield Output(value=([data], schema), metadata={"record_count": len(data)})

    @asset(
        key=[code_location, "google", "directory", "users"],
        io_manager_key="io_manager_gcs_avro",
    )
    def users(
        context: AssetExecutionContext, google_directory: GoogleDirectoryResource
    ):
        data = google_directory.list_users(projection="full")
        schema = get_avro_record_schema(name="users", fields=ASSET_FIELDS["users"])

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

    @asset(
        key=[code_location, "google", "directory", "groups"],
        io_manager_key="io_manager_gcs_avro",
    )
    def groups(
        context: AssetExecutionContext, google_directory: GoogleDirectoryResource
    ):
        data = google_directory.list_groups()
        schema = get_avro_record_schema(name="groups", fields=ASSET_FIELDS["groups"])

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

    @asset(
        key=[code_location, "google", "directory", "roles"],
        io_manager_key="io_manager_gcs_avro",
    )
    def roles(
        context: AssetExecutionContext, google_directory: GoogleDirectoryResource
    ):
        data = google_directory.list_roles()
        schema = get_avro_record_schema(name="roles", fields=ASSET_FIELDS["roles"])

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

    @asset(
        key=[code_location, "google", "directory", "role_assignments"],
        io_manager_key="io_manager_gcs_avro",
    )
    def role_assignments(
        context: AssetExecutionContext, google_directory: GoogleDirectoryResource
    ):
        data = google_directory.list_role_assignments()
        schema = get_avro_record_schema(
            name="role_assignments", fields=ASSET_FIELDS["role_assignments"]
        )

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

    return [orgunits, users, groups, roles, role_assignments]


def build_google_directory_partitioned_assets(code_location, partitions_def):
    @asset(
        key=[code_location, "google", "directory", "members"],
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
    )
    def members(
        context: AssetExecutionContext, google_directory: GoogleDirectoryResource
    ):
        data = google_directory.list_members(group_key=context.partition_key)
        schema = get_avro_record_schema(name="members", fields=ASSET_FIELDS["members"])

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

    return [members]
