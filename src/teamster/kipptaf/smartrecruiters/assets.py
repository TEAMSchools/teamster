import pathlib
import time
from io import StringIO

from dagster import (
    AssetExecutionContext,
    AssetsDefinition,
    Output,
    asset,
    config_from_files,
)
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)

from .. import CODE_LOCATION
from .resources import SmartRecruitersResource
from .schema import ASSET_FIELDS


def build_smartrecruiters_report_asset(
    asset_name, code_location, report_id
) -> AssetsDefinition:
    asset_key = [code_location, "smartrecruiters", asset_name]

    @asset(
        key=[code_location, "smartrecruiters", asset_name],
        metadata={"report_id": report_id},
        io_manager_key="io_manager_gcs_avro",
        group_name="smartrecruiters",
        compute_kind="smartrecruiters",
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(
        context: AssetExecutionContext, smartrecruiters: SmartRecruitersResource
    ):
        report_name = context.asset_key.path[-1]
        report_endpoint = (
            "reporting-api/v201804/reports/"
            + context.assets_def.metadata_by_key[context.asset_key]["report_id"]
            + "/files"
        )

        context.log.info(f"Executing {report_name}")
        report_execution_data = smartrecruiters.post(endpoint=report_endpoint).json()

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
        # context.log.debug(df.dtypes)

        records = df.to_dict(orient="records")
        schema = ASSET_FIELDS[asset_name]

        yield Output(value=(records, schema), metadata={"records": df.shape[0]})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset


smartrecruiters_report_assets = [
    build_smartrecruiters_report_asset(code_location=CODE_LOCATION, **a)
    for a in config_from_files(
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
    )["assets"]
]

_all = [
    *smartrecruiters_report_assets,
]
