from io import StringIO

from dagster import AssetExecutionContext, Output, asset
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)
from teamster.libraries.amplify.mclass.resources import MClassResource


def build_mclass_asset(asset_key, dyd_payload, partitions_def, schema):
    @asset(
        key=asset_key,
        metadata={"dyd_payload": dyd_payload},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        group_name="amplify",
        kinds={"python"},
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, mclass: MClassResource):
        response = mclass.post(
            path="reports/api/report/downloadyourdata",
            data={
                "data": {
                    **dyd_payload,
                    "result": "download_your_data",
                    "years": str(int(context.partition_key[2:4]) - 1),
                }
            },
        )

        if "NO_DATA" in response.text:
            raise Exception(response.json())

        df = read_csv(filepath_or_buffer=StringIO(response.text), low_memory=False)

        df.replace({nan: None}, inplace=True)
        df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

        records = df.to_dict(orient="records")

        yield Output(value=(records, schema), metadata={"records": df.shape[0]})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
