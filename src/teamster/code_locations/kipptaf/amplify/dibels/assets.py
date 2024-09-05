from datetime import datetime
from io import StringIO

from dagster import AssetExecutionContext, Output, asset
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.amplify.dibels.schema import DATA_FARMING_SCHEMA
from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.amplify.dibels.resources import DibelsDataSystemResource


@asset(
    key=[CODE_LOCATION, "amplify", "dibels", "data_farming"],
    io_manager_key="io_manager_gcs_avro",
    group_name="amplify",
    compute_kind="python",
    check_specs=[
        build_check_spec_avro_schema_valid(
            [CODE_LOCATION, "amplify", "dibels", "data_farming"]
        )
    ],
    partitions_def=FiscalYearPartitionsDefinition(
        start_date="2024-07-01", start_month=7, timezone=LOCAL_TIMEZONE.name
    ),
)
def data_farming(context: AssetExecutionContext, dds: DibelsDataSystemResource):
    partition_key_datetime = datetime.strptime(context.partition_key, "%Y-%m-%d")

    response = dds.report(
        report="DataFarming",
        scope="District",
        grade="_ALL_",
        start_year=partition_key_datetime.year,
        end_year=partition_key_datetime.year,
        assessment_period="_ALL_",
        student_filter="any",
        district=18095,  # KIPP Team and Family
        assessment=15030,  # DIBELS 8th Edition
        delimiter=0,  # Comma separated
        # growth_measure=16240,  # Composite
        fields=[
            # 1,  # Student Name
            2,  # Student ID
            # 3,  # Secondary ID
            # 4,  # Date of Birth
            # 5,  # Demographics
            # 21,  # Schools
            # 22,  # Class Names
            # 23,  # Secondary Class Names
            # 25,  # Teacher Names
            # 26,  # District IDs
            # 27,  # School IDs
            41,  # Benchmark Statuses
            43,  # School Percentiles
            44,  # District Percentiles
            45,  # National DDS Percentiles
            47,  # Outcome Measures
            48,  # Assessment Dates
            # 49,  # Assessment Forms
            # 51,  # Remote Testing Status
            # 50,  # Zones of Growth (must select all periods)
            # 61,  # Move Out Dates
            # 62,  # Data System Internal IDs
        ],
    )

    df = read_csv(filepath_or_buffer=StringIO(response.text), low_memory=False)

    df.replace({nan: None}, inplace=True)
    df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

    records = df.to_dict(orient="records")

    yield Output(
        value=(records, DATA_FARMING_SCHEMA), metadata={"row_count": df.shape[0]}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=records, schema=DATA_FARMING_SCHEMA
    )


assets = [
    data_farming,
]
