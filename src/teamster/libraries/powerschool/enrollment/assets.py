from dagster import AssetExecutionContext, DynamicPartitionsDefinition, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)


def build_ps_enrollment_submission_records_asset(
    code_location: str, partitions_def: DynamicPartitionsDefinition, schema: dict
):
    @asset(
        key=[code_location, "powerschool", "enrollment", "submission_records"],
        io_manager_key="io_manager_gcs_avro",
        group_name="powerschool",
        partitions_def=partitions_def,
        check_specs=[
            build_check_spec_avro_schema_valid(
                [code_location, "powerschool", "enrollment", "submission_records"]
            )
        ],
    )
    def _asset(
        context: AssetExecutionContext, ps_enrollment: PowerSchoolEnrollmentResource
    ):
        data = ps_enrollment.list(
            endpoint=f"publishedactions/{context.partition_key}/submissionrecords"
        )

        yield Output(value=(data, schema), metadata={"records": len(data)})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
