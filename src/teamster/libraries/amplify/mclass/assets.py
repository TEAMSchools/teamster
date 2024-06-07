from io import StringIO

from dagster import AssetExecutionContext, Output, asset
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.libraries.amplify.mclass.resources import MClassResource
from teamster.libraries.core.asset_checks import (
    build_check_spec_avro_schema_valid,
    check_avro_schema_valid,
)


def build_mclass_asset(asset_key, dyd_payload, partitions_def, schema, op_tags=None):
    @asset(
        key=asset_key,
        metadata={"dyd_payload": dyd_payload},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        group_name="amplify",
        compute_kind="python",
        op_tags=op_tags,
        check_specs=[build_check_spec_avro_schema_valid(asset_key)],
    )
    def _asset(context: AssetExecutionContext, mclass: MClassResource):
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

        yield Output(value=(records, schema), metadata={"records": df.shape[0]})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset
