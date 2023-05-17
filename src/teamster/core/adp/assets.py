import time
from io import StringIO

from dagster import (
    AssetsDefinition,
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    ResourceParam,
    StaticPartitionsDefinition,
    asset,
)
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.adp.resources import WorkforceManagerResource
from teamster.core.adp.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_wfm_asset(
    asset_name,
    code_location,
    source_system,
    symbolic_ids,
    hyperfind,
    op_tags={},
) -> AssetsDefinition:
    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        metadata={"hyperfind": hyperfind},
        partitions_def=MultiPartitionsDefinition(
            {
                "symbolic_id": StaticPartitionsDefinition(symbolic_ids),
                "date": DynamicPartitionsDefinition(
                    name=f"{code_location}__{source_system}__{asset_name}_date"
                ),
            }
        ),
        io_manager_key="gcs_avro_io",
        op_tags=op_tags,
        output_required=False,
    )
    def _asset(
        context: OpExecutionContext, adp_wfm: ResourceParam[WorkforceManagerResource]
    ):
        asset = context.assets_def
        symbolic_id = context.partition_key.keys_by_dimension["symbolic_id"]

        report_name = asset.key.path[-1]

        symbolic_period_record = [
            sp
            for sp in adp_wfm.request(
                method="GET", endpoint="v1/commons/symbolicperiod"
            ).json()
            if sp["symbolicId"] == symbolic_id
        ][0]

        hyperfind_record = [
            hq
            for hq in (
                adp_wfm.request(method="GET", endpoint="v1/commons/hyperfind")
                .json()
                .get("hyperfindQueries")
            )
            if hq["name"] == asset.metadata_by_key[asset.key]["hyperfind"]
        ][0]

        context.log.info(
            f"Executing {report_name}:\n{symbolic_period_record}\n{hyperfind_record}"
        )

        report_execution_response = adp_wfm.request(
            method="POST",
            endpoint=f"v1/platform/reports/{report_name}/execute",
            json={
                "parameters": [
                    {"name": "DataSource", "value": {"hyperfind": hyperfind_record}},
                    {
                        "name": "DateRange",
                        "value": {"symbolicPeriod": symbolic_period_record},
                    },
                    {
                        "name": "Output Format",
                        "value": {"key": "csv", "title": "CSV"},
                    },  # undocumented: where does this come from?
                ]
            },
        ).json()

        context.log.info(report_execution_response)

        report_execution_id = report_execution_response.get("id")

        while True:
            report_execution_record = [
                rex
                for rex in adp_wfm.request(
                    method="GET", endpoint="v1/platform/report_executions"
                ).json()
                if rex.get("id") == report_execution_id
            ][0]

            context.log.info(report_execution_record)

            if report_execution_record.get("status").get("qualifier") == "Completed":
                context.log.info(f"Downloading {report_name}")

                report_file_text = adp_wfm.request(
                    method="GET",
                    endpoint=(
                        f"v1/platform/report_executions/{report_execution_id}/file"
                    ),
                ).text

                break

            time.sleep(5)

        df = read_csv(filepath_or_buffer=StringIO(report_file_text), low_memory=False)

        df.replace({nan: None}, inplace=True)
        df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        row_count = df.shape[0]

        if row_count > 0:
            yield Output(
                value=(
                    df.to_dict(orient="records"),
                    get_avro_record_schema(
                        name=asset_name, fields=ASSET_FIELDS[asset_name]
                    ),
                ),
                metadata={"records": row_count},
            )

    return _asset
