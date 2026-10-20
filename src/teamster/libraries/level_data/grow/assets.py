from datetime import datetime, timedelta

from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    Output,
    asset,
)
from dagster_shared import check

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.level_data.grow.resources import GrowResource


def normalize_regional_admin_schools(records: list[dict]) -> None:
    """Coerce each user's `regionalAdminSchools` entries to `Ref` records in place.

    Grow returns bare school ids, and some entries arrive as an array serialized
    into an object (`{"0": id, "1": id}`). The Avro schema expects `Ref`
    records, so wrap each id with an empty `name`. Populated `Ref` entries pass
    through unchanged.
    """
    # TODO(#6031): store the field as ids and drop this
    for record in records:
        schools = record.get("regionalAdminSchools")

        if not schools:
            continue

        normalized = []

        for school in schools:
            if isinstance(school, str):
                normalized.append({"_id": school, "name": None})
            elif isinstance(school, dict) and "_id" not in school:
                normalized.extend({"_id": i, "name": None} for i in school.values())
            else:
                normalized.append(school)

        record["regionalAdminSchools"] = normalized


def build_grow_asset(
    asset_key, endpoint, partitions_def, schema, op_tags=None
) -> AssetsDefinition:
    @asset(
        key=asset_key,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        group_name="level_data",
        kinds={"python"},
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
        op_tags=op_tags,
    )
    def _asset(context: AssetExecutionContext, grow: GrowResource):
        if isinstance(context.assets_def.partitions_def, MultiPartitionsDefinition):
            partition_key = check.inst(context.partition_key, MultiPartitionKey)

            archived_key = partition_key.keys_by_dimension["archived"]
            last_modified_key = partition_key.keys_by_dimension["last_modified"]

            last_modified_datetime = datetime.fromisoformat(last_modified_key)

            last_modified_end = last_modified_datetime.replace(
                hour=23, minute=59, second=59, microsecond=999999
            ).timestamp()

            last_modified_start = (
                last_modified_datetime - timedelta(days=1)
            ).timestamp()

            last_modified_def = (
                context.assets_def.partitions_def.get_partitions_def_for_dimension(
                    "last_modified"
                )
            )

            if last_modified_key == last_modified_def.get_last_partition_key():
                last_modified_key = last_modified_start
            elif last_modified_key == last_modified_def.get_first_partition_key():
                last_modified_key = f"0,{last_modified_end}"
            else:
                last_modified_key = f"{last_modified_start},{last_modified_end}"
        else:
            archived_key = context.partition_key
            last_modified_key = None

        endpoint_content = grow.get(
            endpoint=endpoint,
            archived=(archived_key == "t"),
            lastModified=last_modified_key,
        )

        records = endpoint_content["data"]

        if endpoint == "users":
            normalize_regional_admin_schools(records)

        yield Output(
            value=(records, schema), metadata={"records": endpoint_content["count"]}
        )

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
