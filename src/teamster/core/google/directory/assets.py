from dagster import AssetExecutionContext, Output, asset

from teamster.core.google.directory.resources import GoogleDirectoryResource
from teamster.core.google.directory.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_google_directory_assets(code_location):
    @asset(
        key=[code_location, "google", "directory", "users"],
        io_manager_key="gcs_avro_io",
    )
    def _asset(
        context: AssetExecutionContext, google_directory: GoogleDirectoryResource
    ):
        data = google_directory.list_users(projection="full")
        schema = get_avro_record_schema(name="users", fields=ASSET_FIELDS["users"])

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

    return _asset
