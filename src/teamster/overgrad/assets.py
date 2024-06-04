from dagster import (
    AssetExecutionContext,
    DynamicPartitionsDefinition,
    Output,
    _check,
    asset,
)

from teamster.overgrad.resources import OvergradResource

# from teamster.core.utils.functions import (
#     check_avro_schema_valid,
#     get_avro_schema_valid_check_spec,
# )


def build_overgrad_asset(
    endpoint, schema, partitions_def=None, auto_materialize_policy=None
):
    @asset(
        key=["overgrad", endpoint],
        io_manager_key="io_manager_gcs_avro",
        group_name="overgrad",
        # check_specs=[get_avro_schema_valid_check_spec(["overgrad", endpoint])],
        partitions_def=partitions_def,
        auto_materialize_policy=auto_materialize_policy,
    )
    def _asset(context: AssetExecutionContext, overgrad: OvergradResource):
        if context.assets_def.partitions_def is not None:
            response_json = overgrad.get(endpoint, context.partition_key).json()

            data = [response_json["data"]]
        else:
            data = overgrad.get_list(path=endpoint)

        if endpoint in ["admissions", "followings"]:
            partitions_def = _check.inst(
                obj=context.assets_def.partitions_def, ttype=DynamicPartitionsDefinition
            )
            university_ids = set()

            for d in data:
                university_id = d["university"]["id"]

                if university_id is not None:
                    university_ids.add(university_id)

            context.instance.add_dynamic_partitions(
                partitions_def_name=_check.not_none(value=partitions_def.name),
                partition_keys=list(university_ids),
            )

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

        # yield check_avro_schema_valid(
        #     asset_key=context.asset_key, records=data, schema=schema
        # )

    return _asset
