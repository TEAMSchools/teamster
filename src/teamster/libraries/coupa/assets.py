from dagster import AssetExecutionContext, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.coupa.resources import CoupaResource


def build_coupa_asset(code_location, resource, schema):
    asset_key = [code_location, "coupa", resource]

    @asset(
        key=asset_key,
        io_manager_key="io_manager_gcs_avro",
        group_name="coupa",
        kinds={"python"},
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, coupa: CoupaResource):
        records = coupa.get(resource=resource).json()

        yield Output(value=(records, schema), metadata={"record_count": len(records)})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
