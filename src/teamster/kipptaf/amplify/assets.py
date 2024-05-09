from io import StringIO

from dagster import MAX_RUNTIME_SECONDS_TAG, AssetExecutionContext, Output, asset
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .resources import MClassResource
from .schema import ASSET_SCHEMA

PARTITIONS_DEF = FiscalYearPartitionsDefinition(
    start_date="2022-07-01", timezone=LOCAL_TIMEZONE.name, start_month=7
)

DYD_PAYLOAD = {
    "accounts": "1300588536",
    "districts": "1300588535",
    "roster_option": "2",  # On Test Day
    "dyd_assessments": "7_D8",  # DIBELS 8th Edition
    "tracking_id": None,
}


def build_mclass_asset(name, dyd_results, op_tags=None):
    asset_key = [CODE_LOCATION, "amplify", name]
    dyd_payload = {**DYD_PAYLOAD, "dyd_results": dyd_results}

    @asset(
        key=[CODE_LOCATION, "amplify", name],
        metadata={"dyd_payload": dyd_payload},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=PARTITIONS_DEF,
        group_name="amplify",
        compute_kind="python",
        op_tags=op_tags,
        check_specs=[get_avro_schema_valid_check_spec(asset_key)],
    )
    def _asset(context: AssetExecutionContext, mclass: MClassResource):
        asset_name = context.asset_key.path[-1]

        response = mclass.post(
            path="reports/api/report/downloadyourdata",
            data={
                "data": {
                    **dyd_payload,
                    "years": str(int(context.partition_key[2:4]) - 1),
                }
            },
        )

        df = read_csv(filepath_or_buffer=StringIO(response.text), low_memory=False)

        df.replace({nan: None}, inplace=True)
        df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        records = df.to_dict(orient="records")
        schema = ASSET_SCHEMA[asset_name]

        yield Output(value=(records, schema), metadata={"records": df.shape[0]})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset


benchmark_student_summary = build_mclass_asset(
    name="benchmark_student_summary",
    dyd_results="BM",
    op_tags={MAX_RUNTIME_SECONDS_TAG: (60 * 15)},
)

pm_student_summary = build_mclass_asset(name="pm_student_summary", dyd_results="PM")

_all = [
    benchmark_student_summary,
    pm_student_summary,
]
