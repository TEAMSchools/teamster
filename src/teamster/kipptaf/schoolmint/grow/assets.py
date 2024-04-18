import pendulum
from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    asset,
    config_from_files,
)

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)
from teamster.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.kipptaf.schoolmint.grow.resources import SchoolMintGrowResource
from teamster.kipptaf.schoolmint.grow.schema import ASSET_SCHEMA


def build_schoolmint_grow_asset(asset_name, partitions_def) -> AssetsDefinition:
    asset_key = [
        CODE_LOCATION,
        "schoolmint",
        "grow",
        asset_name.replace("-", "_").replace("/", "_"),
    ]

    @asset(
        key=asset_key,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        group_name="schoolmint",
        compute_kind="schoolmint_grow",
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(context: AssetExecutionContext, schoolmint_grow: SchoolMintGrowResource):
        if isinstance(context.assets_def.partitions_def, MultiPartitionsDefinition):
            keys_by_dimension = context.partition_key.keys_by_dimension  # type: ignore

            archived_partition = keys_by_dimension["archived"]
            last_modified_partition = (
                pendulum.from_format(
                    string=keys_by_dimension["last_modified"], fmt="YYYY-MM-DD"
                )
                .subtract(days=1)
                .timestamp()
            )
        else:
            archived_partition = context.partition_key
            last_modified_partition = None

        # TODO: lastModified == None for first partition

        endpoint_content = schoolmint_grow.get(
            endpoint=asset_name,
            archived=(archived_partition == "t"),
            lastModified=last_modified_partition,
        )

        records = endpoint_content["data"]
        schema = ASSET_SCHEMA[asset_name]

        yield Output(
            value=(records, schema), metadata={"records": endpoint_content["count"]}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset


STATIC_PARTITONS_DEF = StaticPartitionsDefinition(["t", "f"])

config_dir = f"src/teamster/{CODE_LOCATION}/schoolmint/grow/config"

static_partition_assets = [
    build_schoolmint_grow_asset(
        asset_name=e["asset_name"], partitions_def=STATIC_PARTITONS_DEF
    )
    for e in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

multi_partition_assets = [
    build_schoolmint_grow_asset(
        asset_name=e["asset_name"],
        partitions_def=MultiPartitionsDefinition(
            {
                "archived": STATIC_PARTITONS_DEF,
                "last_modified": DailyPartitionsDefinition(
                    start_date=e["start_date"],
                    timezone=LOCAL_TIMEZONE.name,
                    end_offset=1,
                ),
            }
        ),
    )
    for e in config_from_files([f"{config_dir}/multi-partition-assets.yaml"])[
        "endpoints"
    ]
]

_all = [
    *static_partition_assets,
    *multi_partition_assets,
]
