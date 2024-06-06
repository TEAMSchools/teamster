from dagster import AssetExecutionContext, DynamicPartitionsDefinition, Output, asset

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.google.forms.schema import (
    FORM_SCHEMA,
    RESPONSES_SCHEMA,
)
from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.google.forms.resources import GoogleFormsResource

GOOGLE_FORMS_PARTITIONS_DEF = DynamicPartitionsDefinition(
    name=f"{CODE_LOCATION}_google_forms_form_ids"
)

key_prefix = [CODE_LOCATION, "google", "forms"]
asset_kwargs = {
    "io_manager_key": "io_manager_gcs_avro",
    "group_name": "google_forms",
    "compute_kind": "python",
    "partitions_def": GOOGLE_FORMS_PARTITIONS_DEF,
}


@asset(
    key=[*key_prefix, "form"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "form"])],
    **asset_kwargs,
)
def form(context: AssetExecutionContext, google_forms: GoogleFormsResource):
    data = google_forms.get_form(form_id=context.partition_key)

    yield Output(value=([data], FORM_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=[data], schema=FORM_SCHEMA
    )


@asset(
    key=[*key_prefix, "responses"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "responses"])],
    **asset_kwargs,
)
def responses(context: AssetExecutionContext, google_forms: GoogleFormsResource):
    reponses = google_forms.list_responses(form_id=context.partition_key)

    yield Output(
        value=(reponses, RESPONSES_SCHEMA), metadata={"record_count": len(reponses)}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=reponses, schema=RESPONSES_SCHEMA
    )


assets = [
    form,
    responses,
]
