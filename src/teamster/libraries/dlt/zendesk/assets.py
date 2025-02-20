from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt import pipeline
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery

from teamster.libraries.dlt.zendesk.pipeline import zendesk_support
from teamster.libraries.dlt.zendesk.pipeline.helpers.credentials import (
    TZendeskCredentials,
)


class ZendeskDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        return super().__init__()

    def get_asset_spec(self, data):
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=[self.code_location, "dlt", "zendesk", "support", data.resource.name],
            deps=[],
        )

        return asset_spec


def build_zendesk_support_dlt_assets(
    zendesk_credentials: TZendeskCredentials,
    dlt_credentials: dict,
    code_location: str,
    op_tags: dict[str, object] | None = None,
):
    if op_tags is None:
        op_tags = {}

    dlt_source = zendesk_support(credentials=zendesk_credentials, load_all=True)

    dlt_pipeline = pipeline(
        pipeline_name="zendesk",
        destination=bigquery(),
        dataset_name=f"dagster_{code_location}_dlt_zendesk_support",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source,
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__dlt__zendesk__support",
        group_name="zendesk",
        dagster_dlt_translator=ZendeskDagsterDltTranslator(code_location),
        op_tags=op_tags,
    )
    def _assets(context: AssetExecutionContext, dlt: DagsterDltResource):
        yield from dlt.run(context=context, credentials=dlt_credentials)

    return _assets
