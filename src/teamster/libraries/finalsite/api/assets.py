from dagster import AssetExecutionContext, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.finalsite.api.resources import FinalsiteResource


def build_finalsite_asset(
    code_location: str, asset_name: str, schema, params: dict | None = None
):
    key = [code_location, "finalsite", asset_name]

    @asset(
        key=key,
        io_manager_key="io_manager_gcs_avro",
        # partitions_def=partitions_def,
        check_specs=[build_check_spec_avro_schema_valid(key)],
        group_name="finalsite",
        # One shared pool across ALL districts (not per-location): the Finalsite
        # gateway throttles by source IP, so simultaneous pulls from the shared
        # egress IP return 403 even with separate subdomains and credentials.
        # Set this pool's limit to 1 in Dagster+ to serialize them. See #4408.
        pool="finalsite_api",
        kinds={"python"},
    )
    def _asset(context: AssetExecutionContext, finalsite: FinalsiteResource):
        data = finalsite.list(path=asset_name, params=params or {})

        yield Output(value=(data, schema), metadata={"record_count": len(data)})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
