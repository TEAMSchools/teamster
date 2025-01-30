import json

from dagster import AssetExecutionContext, AssetKey
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

    def get_asset_key(self, resource):
        return AssetKey(
            [self.code_location, "dlt", "zendesk", "support", resource.name]
        )

    def get_deps_asset_keys(self, resource):
        return []

    def get_kinds(self, resource, destination):
        return {"dlt", destination.destination_name}


def build_zendesk_support_dlt_assets(
    credentials: TZendeskCredentials,
    code_location: str,
    op_tags: dict[str, object] | None = None,
):
    if op_tags is None:
        op_tags = {}

    dlt_source = zendesk_support(credentials=credentials, load_all=True)

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
        yield from dlt.run(
            context=context,
            credentials=json.load(
                fp=open(file="/etc/secret-volume/gcloud_teamster_dlt_keyfile.json")
            ),
            write_disposition="replace",
        )

    return _assets
