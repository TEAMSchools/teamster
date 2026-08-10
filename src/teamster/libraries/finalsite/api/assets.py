from datetime import date, timedelta

from dagster import AssetExecutionContext, Config, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.finalsite.api.resources import FinalsiteResource


def get_finalsite_since(partition_key: str) -> str:
    """Return the `since` date for a pull, one day before the partition date.

    The API's `since` is date-grained, so the finest possible increment is one
    day. Subtracting a safety day means a run that straddles midnight or hits a
    vendor clock skew cannot drop records, and it makes every pull on a given
    date a superset of any earlier pull on that date — which is what lets the
    midday run overwrite the overnight run's partition safely. Measured cost on
    kippmiami: 43 extra records, 2 extra pages.
    """
    return (date.fromisoformat(partition_key) - timedelta(days=1)).isoformat()


class FinalsiteContactsConfig(Config):
    """Run config for a contacts pull.

    `full_pull` omits `since` entirely, pulling every contact. Used once per
    district to seed the first partition; a `since` pull alone would leave
    staging holding only contacts that changed after go-live.
    """

    full_pull: bool = False


def build_finalsite_asset(
    code_location: str,
    asset_name: str,
    schema,
    params: dict | None = None,
    partitions_def=None,
):
    key = [code_location, "finalsite", asset_name]

    @asset(
        key=key,
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        check_specs=[build_check_spec_avro_schema_valid(key)],
        group_name="finalsite",
        # One shared pool across ALL districts (not per-location): the Finalsite
        # gateway throttles by source IP, so simultaneous pulls from the shared
        # egress IP return 403 even with separate subdomains and credentials.
        # Set this pool's limit to 1 in Dagster+ to serialize them. See #4408.
        pool="finalsite_api",
        kinds={"python"},
    )
    def _asset(
        context: AssetExecutionContext,
        finalsite: FinalsiteResource,
        config: FinalsiteContactsConfig,
    ):
        request_params = {**(params or {})}

        # A partitioned asset pulls incrementally: the partition key IS the
        # watermark, so a failed run writes no partition and advances nothing.
        # `full_pull` is the seed escape hatch.
        if partitions_def is not None and not config.full_pull:
            request_params["since"] = get_finalsite_since(context.partition_key)

        data = finalsite.list(path=asset_name, params=request_params)

        yield Output(
            value=(data, schema),
            metadata={
                "record_count": len(data),
                "since": request_params.get("since", "FULL PULL"),
            },
        )
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
