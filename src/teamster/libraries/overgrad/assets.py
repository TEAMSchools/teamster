from datetime import UTC, datetime

from dagster import AssetExecutionContext, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.overgrad.resources import OvergradResource

# list endpoints that support the `updated_after` filter
CURSOR_ENDPOINTS = {"students", "admissions", "followings"}


def _parse_updated_at(record: dict) -> datetime:
    updated_at = record.get("updated_at")

    if updated_at is None:
        return datetime.min.replace(tzinfo=UTC)

    parsed = datetime.fromisoformat(updated_at)

    # Overgrad sends UTC; read a timestamp without a marker as UTC too
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def merge_by_id(records: list[dict]) -> list[dict]:
    """Reduce a pull to one record per `id`.

    Where an `id` repeats, the copy with the later `updated_at` wins; a missing
    `updated_at` loses to any dated copy. Records without an `id` cannot be
    matched, so they pass through unmerged.
    """
    merged: dict[int, dict] = {}
    no_id: list[dict] = []

    for record in records:
        if record.get("id") is None:
            no_id.append(record)
            continue

        current = merged.get(record["id"])

        if current is None or _parse_updated_at(record) > _parse_updated_at(current):
            merged[record["id"]] = record

    return [*merged.values(), *no_id]


def build_overgrad_asset(
    code_location: str,
    name: str,
    schema,
    partitions_def=None,
    automation_condition=None,
    deps: list | None = None,
    pool: str | None = None,
):
    key = [code_location, "overgrad", name]

    if pool is None:
        pool = f"overgrad_api_limit_{code_location}"

    @asset(
        key=key,
        io_manager_key="io_manager_gcs_avro",
        group_name="overgrad",
        partitions_def=partitions_def,
        automation_condition=automation_condition,
        check_specs=[build_check_spec_avro_schema_valid(key)],
        deps=deps,
        pool=pool,
        kinds={"python"},
    )
    def _asset(context: AssetExecutionContext, overgrad: OvergradResource):
        if context.assets_def.partitions_def is not None:
            response_json = overgrad.get(name, context.partition_key).json()

            data = [response_json["data"]]
        elif name in CURSOR_ENDPOINTS:
            data = merge_by_id(overgrad.list_by_cursor(path=name))
        else:
            data = overgrad.list(path=name)

        if name in ["admissions", "followings"]:
            university_ids = set()

            for d in data:
                university_id = d["university"]["id"]

                if university_id is not None:
                    university_ids.add(str(university_id))

            # best-effort: every run re-registers the full id set, so a Dagster
            # Cloud API blip should not discard an hour of rate-limited pages.
            # ERROR, not WARNING: nothing retries this in-run, and a persistent
            # failure would otherwise stall new university partitions silently
            try:
                context.instance.add_dynamic_partitions(
                    partitions_def_name="overgrad__universities__id",
                    partition_keys=list(university_ids),
                )
            except Exception as e:
                context.log.error(f"Skipped registering university partitions: {e}")

        yield Output(value=(data, schema), metadata={"record_count": len(data)})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
