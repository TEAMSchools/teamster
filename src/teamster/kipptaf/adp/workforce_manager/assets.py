import time
from io import StringIO

from dagster import (
    AssetsDefinition,
    AutoMaterializePolicy,
    DailyPartitionsDefinition,
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    OpExecutionContext,
    Output,
    StaticPartitionsDefinition,
    asset,
)
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)

from ... import CODE_LOCATION, LOCAL_TIMEZONE
from .resources import AdpWorkforceManagerResource
from .schema import ASSET_FIELDS


def build_adp_wfm_asset(
    asset_name,
    report_name,
    hyperfind,
    symbolic_ids,
    date_partitions_def: DailyPartitionsDefinition | DynamicPartitionsDefinition,
) -> AssetsDefinition:
    asset_key = [CODE_LOCATION, "adp_workforce_manager", asset_name]

    @asset(
        key=asset_key,
        metadata={"hyperfind": hyperfind, "report_name": report_name},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=MultiPartitionsDefinition(
            {
                "symbolic_id": StaticPartitionsDefinition(symbolic_ids),
                "date": date_partitions_def,
            }
        ),
        group_name="adp_workforce_manager",
        auto_materialize_policy=AutoMaterializePolicy.eager(),
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(context: OpExecutionContext, adp_wfm: AdpWorkforceManagerResource):
        asset = context.assets_def
        symbolic_id = context.partition_key.keys_by_dimension["symbolic_id"]  # type:ignore

        symbolic_period_record = [
            sp
            for sp in adp_wfm.get(endpoint="v1/commons/symbolicperiod").json()
            if sp["symbolicId"] == symbolic_id
        ][0]

        hyperfind_record = [
            hq
            for hq in (
                adp_wfm.get(endpoint="v1/commons/hyperfind")
                .json()
                .get("hyperfindQueries")
            )
            if hq["name"] == asset.metadata_by_key[asset.key]["hyperfind"]
        ][0]

        context.log.info(
            f"Executing {report_name}:\n{symbolic_period_record}\n{hyperfind_record}"
        )

        report_execution_response = adp_wfm.post(
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
                for rex in adp_wfm.get(endpoint="v1/platform/report_executions").json()
                if rex.get("id") == report_execution_id
            ][0]

            context.log.info(report_execution_record)

            if report_execution_record.get("status").get("qualifier") == "Completed":
                context.log.info(f"Downloading {report_name}")

                report_file_text = adp_wfm.get(
                    endpoint=f"v1/platform/report_executions/{report_execution_id}/file"
                ).text

                break

            time.sleep(5)

        df = read_csv(filepath_or_buffer=StringIO(report_file_text), low_memory=False)

        df.replace({nan: None}, inplace=True)
        df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        row_count = df.shape[0]

        records = df.to_dict(orient="records")
        schema = ASSET_FIELDS[asset_name]

        yield Output(value=(records, schema), metadata={"records": row_count})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset


accrual_reporting_period_summary = build_adp_wfm_asset(
    asset_name="accrual_reporting_period_summary",
    report_name="AccrualReportingPeriodSummary",
    hyperfind="All Home",
    symbolic_ids=["Today"],
    date_partitions_def=DailyPartitionsDefinition(
        start_date="2023-05-17",
        timezone=LOCAL_TIMEZONE.name,
        fmt="%Y-%m-%d",
        end_offset=1,
    ),
)

time_details = build_adp_wfm_asset(
    asset_name="time_details",
    report_name="TimeDetails",
    hyperfind="All Home",
    symbolic_ids=["Previous_SchedPeriod", "Current_SchedPeriod"],
    date_partitions_def=DynamicPartitionsDefinition(
        name=f"{CODE_LOCATION}__adp_workforce_manager__time_details_date"
    ),
)

adp_wfm_assets_daily = [
    accrual_reporting_period_summary,
]

adp_wfm_assets_dynamic = [
    time_details,
]

_all = [
    *adp_wfm_assets_daily,
    *adp_wfm_assets_dynamic,
]
