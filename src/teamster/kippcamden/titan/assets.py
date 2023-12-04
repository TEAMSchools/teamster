import pendulum
from dagster import StaticPartitionsDefinition, config_from_files

from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.titan.schema import ASSET_FIELDS
from teamster.core.utils.classes import FiscalYear
from teamster.core.utils.functions import get_avro_record_schema

from .. import CODE_LOCATION, CURRENT_FISCAL_YEAR, LOCAL_TIMEZONE

__all__ = []

for asset in config_from_files(
    [f"src/teamster/{CODE_LOCATION}/titan/config/assets.yaml"]
)["assets"]:
    start_fy = FiscalYear(
        datetime=pendulum.from_format(
            string=asset["partition_start_date"], fmt="YYYY-MM-DD", tz=LOCAL_TIMEZONE
        ),
        start_month=7,
    )

    partition_keys = [
        str(y - 1)
        for y in range(start_fy.fiscal_year, (CURRENT_FISCAL_YEAR.fiscal_year + 1))
    ]

    asset_name = asset["asset_name"]

    __all__.append(
        build_sftp_asset(
            asset_key=[CODE_LOCATION, "titan", asset_name],
            ssh_resource_key="ssh_titan",
            avro_schema=get_avro_record_schema(
                name=asset_name, fields=ASSET_FIELDS[asset_name]
            ),
            partitions_def=StaticPartitionsDefinition(partition_keys),
            **asset,
        )
    )
