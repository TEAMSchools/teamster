from dagster import AssetExecutionContext, Output, asset

from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.overgrad.resources import OvergradResource


def build_overgrad_asset(
    asset_key,
    schema,
    partitions_def=None,
    auto_materialize_policy=None,
    deps=None,
    universities_partitions_def_name: str | None = None,
):
    endpoint = asset_key[-1]

    @asset(
        key=asset_key,
        io_manager_key="io_manager_gcs_avro",
        group_name="overgrad",
        partitions_def=partitions_def,
        auto_materialize_policy=auto_materialize_policy,
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        deps=deps,
    )
    def _asset(context: AssetExecutionContext, overgrad: OvergradResource):
        if context.assets_def.partitions_def is not None:
            response_json = overgrad.get(endpoint, context.partition_key).json()

            data = [response_json["data"]]
        else:
            data = overgrad.get_list(path=endpoint)

        if universities_partitions_def_name is not None:
            university_ids = set()

            for d in data:
                university_id = d["university"]["id"]

                if university_id is not None:
                    university_ids.add(str(university_id))

            context.instance.add_dynamic_partitions(
                partitions_def_name=universities_partitions_def_name,
                partition_keys=list(university_ids),
            )

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
