from dagster import AssetExecutionContext, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.overgrad.resources import OvergradResource


def build_overgrad_asset(
    code_location: str,
    name: str,
    schema,
    partitions_def=None,
    automation_condition=None,
    deps=None,
):
    key = [code_location, "overgrad", name]

    @asset(
        key=key,
        io_manager_key="io_manager_gcs_avro",
        group_name="overgrad",
        partitions_def=partitions_def,
        automation_condition=automation_condition,
        check_specs=[build_check_spec_avro_schema_valid(key)],
        deps=deps,
        compute_kind="python",
        op_tags={"dagster/concurrency_key": f"overgrad_api_limit_{code_location}"},
    )
    def _asset(context: AssetExecutionContext, overgrad: OvergradResource):
        if context.assets_def.partitions_def is not None:
            response_json = overgrad.get(name, context.partition_key).json()

            data = [response_json["data"]]
        else:
            data = overgrad.get_list(path=name)

        if name in ["admissions", "followings"]:
            university_ids = set()

            for d in data:
                university_id = d["university"]["id"]

                if university_id is not None:
                    university_ids.add(str(university_id))

            context.instance.add_dynamic_partitions(
                partitions_def_name="overgrad__universities__id",
                partition_keys=list(university_ids),
            )

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
