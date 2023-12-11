from io import StringIO

from dagster import AssetExecutionContext, Output, asset, config_from_files
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.core.utils.functions import (
    check_avro_schema_valid,
    get_avro_record_schema,
    get_avro_schema_valid_check_spec,
)

from .. import CODE_LOCATION, LOCAL_TIMEZONE
from .resources import MClassResource
from .schema import ASSET_FIELDS


def build_mclass_asset(name, partitions_def, dyd_payload):
    asset_key = [CODE_LOCATION, "amplify", name]

    @asset(
        key=[CODE_LOCATION, "amplify", name],
        metadata={"dyd_payload": dyd_payload},
        io_manager_key="io_manager_gcs_avro",
        partitions_def=partitions_def,
        group_name="amplify",
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
        schema = get_avro_record_schema(
            name=asset_name, fields=ASSET_FIELDS[asset_name]
        )

        yield Output(value=(records, schema), metadata={"records": df.shape[0]})

        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=records, schema=schema
        )

    return _asset


mclass_assets = [
    build_mclass_asset(
        name=a["name"],
        dyd_payload=a["dyd_payload"],
        partitions_def=FiscalYearPartitionsDefinition(
            start_date=a["partition_start_date"],
            timezone=LOCAL_TIMEZONE.name,
            start_month=7,
        ),
    )
    for a in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/amplify/config/assets.yaml"]
    )["assets"]
]

__all__ = [
    *mclass_assets,
]
