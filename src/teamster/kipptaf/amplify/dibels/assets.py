from io import StringIO

from dagster import AssetExecutionContext, Output, asset
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.amplify.dibels.resources import DibelsDataSystemResource
from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_schema_valid_check_spec,
)
from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.amplify.dibels.schema import DATA_FARMING_SCHEMA


@asset(
    key=[CODE_LOCATION, "amplify", "dibels", "data_farming"],
    io_manager_key="io_manager_gcs_avro",
    group_name="amplify",
    compute_kind="python",
    check_specs=[
        get_avro_schema_valid_check_spec(
            [CODE_LOCATION, "amplify", "dibels", "data_farming"]
        )
    ],
    # partitions_def=partitions_def,
)
def data_farming(context: AssetExecutionContext, dds: DibelsDataSystemResource):
    response = dds.report(
        report="DataFarming",
        scope="District",
        district=109,
        grade="_ALL_",
        start_year=2023,
        end_year=2023,
        assessment=15030,
        assessment_period="_ALL_",
        student_filter="none",
        growth_measure=16240,
        delimiter=0,
        fields=[
            1,
            2,
            3,
            4,
            5,
            21,
            22,
            23,
            25,
            26,
            27,
            41,
            43,
            44,
            45,
            47,
            48,
            49,
            51,
            50,
            61,
            62,
        ],
    )

    df = read_csv(filepath_or_buffer=StringIO(response.text), low_memory=False)

    df.replace({nan: None}, inplace=True)
    df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

    records = df.to_dict(orient="records")

    import json
    import pathlib

    fp = pathlib.Path("env/amplify/datafarming.json")
    fp.parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj=records, fp=fp.open("w"))

    yield Output(
        value=(records, DATA_FARMING_SCHEMA), metadata={"row_count": df.shape[0]}
    )

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=records, schema=DATA_FARMING_SCHEMA
    )


assets = [
    data_farming,
]
