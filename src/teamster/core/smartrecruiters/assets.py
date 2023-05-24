import time
from io import StringIO

from dagster import AssetsDefinition, OpExecutionContext, Output, asset
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.smartrecruiters.resources import SmartRecruitersResource
from teamster.core.smartrecruiters.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema


def build_smartrecruiters_report_asset(
    asset_name,
    code_location,
    source_system,
    report_id,
    op_tags={},
) -> AssetsDefinition:
    @asset(
        name=asset_name,
        key_prefix=[code_location, source_system],
        metadata={"report_id": report_id},
        io_manager_key="gcs_avro_io",
        op_tags=op_tags,
        output_required=False,
    )
    def _asset(context: OpExecutionContext, smartrecruiters: SmartRecruitersResource):
        asset = context.assets_def

        report_name = asset.key.path[-1]
        report_endpoint = (
            "reporting-api/v201804/reports/"
            + asset.metadata_by_key[asset.key]["report_id"]
            + "/files"
        )

        context.log.info(f"Executing {report_name}")
        report_execution_data = smartrecruiters.post(endpoint=report_endpoint).json()

        context.log.info(report_execution_data)
        report_file_id = report_execution_data["reportFileId"]
        report_file_status = report_execution_data["reportFileStatus"]

        while report_file_status != "COMPLETED":
            report_files_data = smartrecruiters.get(endpoint=report_endpoint).json()

            report_file_record = [
                rf
                for rf in report_files_data["content"]
                if rf["reportFileId"] == report_file_id
            ]

            if report_file_record:
                report_file_status = report_file_record[0]["reportFileStatus"]

            context.log.info(report_file_status)
            if report_file_status == "COMPLETED":
                break
            else:
                time.sleep(0.1)  # rate-limit 10 req/sec

        context.log.info(f"Downloading {report_name}")
        report_file_text = smartrecruiters.get(
            endpoint=f"{report_endpoint}/recent/data"
        ).text

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
