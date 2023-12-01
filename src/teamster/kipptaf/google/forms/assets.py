from dagster import AssetExecutionContext, Output, StaticPartitionsDefinition, asset

from teamster.core.utils.functions import get_avro_record_schema

from ... import CODE_LOCATION
from .resources import GoogleFormsResource
from .schema import ASSET_FIELDS

FORM_IDS = [
    "1jpeMof_oQ9NzTw85VFsA5A7G9VrH3XkSc_nZDFz07nA",  # staff info
    "1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0",  # manager
    "1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI",  # support
]

PARTITIONS_DEF = StaticPartitionsDefinition(FORM_IDS)


@asset(
    key=[CODE_LOCATION, "google", "forms", "form"],
    io_manager_key="io_manager_gcs_avro",
    partitions_def=PARTITIONS_DEF,
    group_name="google_forms",
)
def form(context: AssetExecutionContext, google_forms: GoogleFormsResource):
    data = google_forms.get_form(form_id=context.partition_key)
    schema = get_avro_record_schema(name="form", fields=ASSET_FIELDS["form"])

    yield Output(value=([data], schema), metadata={"record_count": len(data)})


@asset(
    key=[CODE_LOCATION, "google", "forms", "responses"],
    io_manager_key="io_manager_gcs_avro",
    partitions_def=PARTITIONS_DEF,
    group_name="google_forms",
)
def responses(context: AssetExecutionContext, google_forms: GoogleFormsResource):
    data = google_forms.list_responses(form_id=context.partition_key)
    schema = get_avro_record_schema(name="responses", fields=ASSET_FIELDS["responses"])

    yield Output(
        value=([data], schema), metadata={"record_count": len(data.get("responses"))}
    )
