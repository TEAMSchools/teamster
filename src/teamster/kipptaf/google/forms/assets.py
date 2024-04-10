from dagster import AssetExecutionContext, Output, StaticPartitionsDefinition, asset

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)

from ... import CODE_LOCATION
from .resources import GoogleFormsResource
from .schema import ASSET_FIELDS

FORM_IDS = [
    "1jpeMof_oQ9NzTw85VFsA5A7G9VrH3XkSc_nZDFz07nA",  # staff info
    "1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0",  # manager
    "1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI",  # support
    "1tuqQIkPX8GfGXdpkNra9shB2Ig_U9CSS7VH1RfuQ_68",  # ITR
    "15xuEO72xhyhhv8K0qKbkSV864-DetXhmWsxKyS7ai50",  # KTAF support
    "1oUBls4Kaj0zcbQyeWowe8Es1BFqunolAPEamzT6enQs",  # Career Launch Survey
    "1IXIrXFLrXDyq9cvjMBhFJB9mV_nxKGUNYUlRbD4ku_A",  # PM Score Change Request Form
]

key_prefix = [CODE_LOCATION, "google", "forms"]
asset_kwargs = {
    "io_manager_key": "io_manager_gcs_avro",
    "group_name": "google_forms",
    "compute_kind": "google_forms",
    "partitions_def": StaticPartitionsDefinition(FORM_IDS),
}


@asset(
    key=[*key_prefix, "form"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "form"])],
    **asset_kwargs,
)
def form(context: AssetExecutionContext, google_forms: GoogleFormsResource):
    data = google_forms.get_form(form_id=context.partition_key)
    schema = ASSET_FIELDS["form"]

    yield Output(value=([data], schema), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=[data], schema=schema
    )


@asset(
    key=[*key_prefix, "responses"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "responses"])],
    **asset_kwargs,
)
def responses(context: AssetExecutionContext, google_forms: GoogleFormsResource):
    data = google_forms.list_responses(form_id=context.partition_key)
    schema = ASSET_FIELDS["responses"]

    yield Output(
        value=([data], schema), metadata={"record_count": len(data.get("responses"))}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=[data], schema=schema
    )


_all = [
    form,
    responses,
]
