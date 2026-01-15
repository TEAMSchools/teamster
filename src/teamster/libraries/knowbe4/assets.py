from dagster import AssetExecutionContext, Output, asset

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.knowbe4.resources import KnowBe4Resource


def build_knowbe4_asset(
    code_location: str, resource: str, schema: dict, params: dict | None = None
):
    if params is None:
        params = {}

    asset_key = [code_location, "knowbe4", *resource.split("/")]

    @asset(
        key=asset_key,
        io_manager_key="io_manager_gcs_avro",
        group_name="knowbe4",
        kinds={"python"},
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, knowbe4: KnowBe4Resource):
        records = knowbe4.list(resource=resource, params=params)

        yield Output(value=(records, schema), metadata={"record_count": len(records)})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
