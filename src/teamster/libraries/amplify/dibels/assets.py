import re
from datetime import datetime
from io import StringIO

from dagster import AssetExecutionContext, MultiPartitionKey, Output, _check, asset
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.amplify.dibels.resources import DibelsDataSystemResource


def build_amplify_dds_report_asset(
    code_location: str, partitions_def, schema, report: str, report_kwargs: dict
):
    asset_name = re.sub(pattern=r"(?<!^)(?=[A-Z])", repl="_", string=report).lower()

    asset_key = [code_location, "amplify", "dibels", asset_name]

    # default kwargs
    report_kwargs.update(
        {
            "report": report,
            "scope": "District",
            "district": 18095,  # KIPP Team and Family
            "assessment": 15030,  # DIBELS 8th Edition
            "delimiter": 0,  # Comma separated
        }
    )

    @asset(
        key=asset_key,
        io_manager_key="io_manager_gcs_avro",
        group_name="amplify",
        compute_kind="python",
        partitions_def=partitions_def,
        metadata=report_kwargs,
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, dds: DibelsDataSystemResource):
        partition_key = _check.inst(obj=context.partition_key, ttype=MultiPartitionKey)

        date_partition_key = datetime.strptime(
            partition_key.keys_by_dimension["date"], "%Y-%m-%d"
        )

        if report == "DataFarming":
            report_kwargs.update(
                {
                    "StartYear": date_partition_key.year,
                    "EndYear": date_partition_key.year,
                }
            )
        elif report == "ProgressExport":
            report_kwargs["SchoolYear"] = date_partition_key.year

        response = dds.report(
            grade=partition_key.keys_by_dimension["grade"], **report_kwargs
        )

        df = read_csv(filepath_or_buffer=StringIO(response.text), low_memory=False)

        df.replace({nan: None}, inplace=True)
        df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        records = df.to_dict(orient="records")

        yield Output(value=(records, schema), metadata={"row_count": df.shape[0]})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
