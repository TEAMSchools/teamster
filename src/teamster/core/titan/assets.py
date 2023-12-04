import pendulum
from dagster import StaticPartitionsDefinition

from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.titan.schema import ASSET_FIELDS
from teamster.core.utils.classes import FiscalYear
from teamster.core.utils.functions import get_avro_record_schema


def build_titan_sftp_asset(
    code_location, config, current_fiscal_year: FiscalYear, timezone
):
    asset_name = config["asset_name"]
    partition_start_date = config["partition_start_date"]

    start_fy = FiscalYear(
        datetime=pendulum.from_format(
            string=partition_start_date, fmt="YYYY-MM-DD", tz=timezone
        ),
        start_month=7,
    )

    partitions_def = StaticPartitionsDefinition(
        [
            str(fy - 1)
            for fy in range(start_fy.fiscal_year, (current_fiscal_year.fiscal_year + 1))
        ]
    )

    return build_sftp_asset(
        asset_key=[code_location, "titan", asset_name],
        ssh_resource_key="ssh_titan",
        avro_schema=get_avro_record_schema(
            name=asset_name, fields=ASSET_FIELDS[asset_name]
        ),
        partitions_def=partitions_def,
        **config,
    )
