import pathlib

import pendulum
from dagster import StaticPartitionsDefinition, config_from_files

from teamster.code_locations.kippnewark import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kippnewark.titan.schema import ASSET_SCHEMA
from teamster.libraries.core.utils.classes import FiscalYear
from teamster.libraries.sftp.assets import build_sftp_asset

assets = []

for asset in config_from_files(
    [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
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

    assets.append(
        build_sftp_asset(
            asset_key=[CODE_LOCATION, "titan", asset_name],
            ssh_resource_key="ssh_titan",
            avro_schema=ASSET_SCHEMA[asset_name],
            partitions_def=StaticPartitionsDefinition(partition_keys),
            **asset,
        )
    )
