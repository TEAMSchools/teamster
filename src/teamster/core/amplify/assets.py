from io import StringIO

from dagster import AutoMaterializePolicy, OpExecutionContext, Output, asset
from numpy import nan
from pandas import read_csv
from slugify import slugify

from teamster.core.amplify.resources import MClassResource
from teamster.core.amplify.schema import ASSET_FIELDS
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.core.utils.functions import get_avro_record_schema


def build_mclass_asset(
    name,
    code_location,
    source_system,
    partition_start_date,
    timezone,
    dyd_payload,
    freshness_policy,
    auto_materialize_policy=AutoMaterializePolicy.eager(),
    op_tags={},
):
    @asset(
        name=name,
        key_prefix=[code_location, source_system],
        metadata={"dyd_payload": dyd_payload},
        partitions_def=FiscalYearPartitionsDefinition(
            start_date=partition_start_date, timezone=timezone.name, start_month=7
        ),
        io_manager_key="gcs_avro_io",
        op_tags=op_tags,
        output_required=False,
        freshness_policy=freshness_policy,
        auto_materialize_policy=auto_materialize_policy,
    )
    def _asset(context: OpExecutionContext, mclass: MClassResource):
        asset_name = context.assets_def.key.path[-1]
        asset_metadata = context.assets_def.metadata_by_key[context.assets_def.key]

        response = mclass.post(
            path="reports/api/report/downloadyourdata",
            data={
                "data": {
                    **asset_metadata["dyd_payload"],
                    "years": str(int(context.partition_key[2:4]) - 1),
                }
            },
        )

        df = read_csv(filepath_or_buffer=StringIO(response.text), low_memory=False)

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
