from dagster import AssetExecutionContext, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.finalsite.resources import FinalsiteResource


def build_finalsite_asset(code_location: str, asset_name: str, schema):
    key = [code_location, "finalsite", asset_name]

    @asset(
        key=key,
        io_manager_key="io_manager_gcs_avro",
        # partitions_def=partitions_def,
        check_specs=[build_check_spec_avro_schema_valid(key)],
        group_name="finalsite",
        kinds={"python"},
    )
    def _asset(context: AssetExecutionContext, finalsite: FinalsiteResource):
        data = finalsite.list(path=asset_name)

        yield Output(value=(data, schema), metadata={"record_count": len(data)})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
