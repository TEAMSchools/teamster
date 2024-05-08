from dagster import AssetExecutionContext, DynamicPartitionsDefinition, Output, asset

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)
from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.google.forms.resources import GoogleFormsResource
from teamster.kipptaf.google.forms.schema import ASSET_SCHEMA

GOOGLE_FORMS_PARTITIONS_DEF = DynamicPartitionsDefinition(
    name=f"{CODE_LOCATION}_google_forms_form_ids"
)

key_prefix = [CODE_LOCATION, "google", "forms"]
asset_kwargs = {
    "io_manager_key": "io_manager_gcs_avro",
    "group_name": "google_forms",
    "compute_kind": "google_forms",
    "partitions_def": GOOGLE_FORMS_PARTITIONS_DEF,
}


@asset(
    key=[*key_prefix, "form"],
    check_specs=[get_avro_schema_valid_check_spec([*key_prefix, "form"])],
    **asset_kwargs,
)
def form(context: AssetExecutionContext, google_forms: GoogleFormsResource):
    data = google_forms.get_form(form_id=context.partition_key)
    schema = ASSET_SCHEMA["form"]

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
    schema = ASSET_SCHEMA["responses"]

    yield Output(
        value=([data], schema),
        metadata={"record_count": len(data.get("responses", []))},
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=[data], schema=schema
    )


assets = [
    form,
    responses,
]
