from dagster import AssetExecutionContext, AssetKey
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt import pipeline
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery

from teamster.libraries.dlt.salesforce.pipeline import salesforce_source


class SalesforceDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        return super().__init__()

    def get_asset_spec(self, data):
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=AssetKey([self.code_location, "dlt", "kippadb", data.resource.name]),
            deps=[],
        )

        asset_spec = asset_spec.merge_attributes(kinds={"salesforce"})

        return asset_spec


def build_salesforce_kippadb_dlt_assets(
    salesforce_user_name: str,
    salesforce_password: str,
    salesforce_security_token: str,
    dlt_credentials: dict,
    code_location: str,
    op_tags: dict[str, object] | None = None,
):
    if op_tags is None:
        op_tags = {}

    dlt_source = salesforce_source(
        user_name=salesforce_user_name,
        password=salesforce_password,
        security_token=salesforce_security_token,
    )

    dlt_pipeline = pipeline(
        pipeline_name="kippadb",
        destination=bigquery(),
        dataset_name=f"dagster_{code_location}_dlt_kippadb",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source,
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__dlt__kippadb",
        group_name="kippadb",
        dagster_dlt_translator=SalesforceDagsterDltTranslator(code_location),
        op_tags=op_tags,
    )
    def _assets(context: AssetExecutionContext, dlt: DagsterDltResource):
        yield from dlt.run(context=context, credentials=dlt_credentials)

    return _assets
