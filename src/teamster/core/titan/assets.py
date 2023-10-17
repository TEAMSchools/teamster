import pendulum
from dagster import StaticPartitionsDefinition, config_from_files

from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.titan.schema import ASSET_FIELDS
from teamster.core.utils.classes import FiscalYear
from teamster.core.utils.functions import get_avro_record_schema


def build_titan_sftp_assets(code_location, fiscal_year, timezone):
    sftp_assets = []

    for a in config_from_files(
        [f"src/teamster/{code_location}/titan/config/assets.yaml"]
    )["assets"]:
        start_fy = FiscalYear(
            datetime=pendulum.from_format(
                string=a["partition_start_date"], fmt="YYYY-MM-DD", tz=timezone
            ),
            start_month=7,
        )

        partitions_def = StaticPartitionsDefinition(
            [
                str(fy - 1)
                for fy in range(start_fy.fiscal_year, (fiscal_year.fiscal_year + 1))
            ]
        )

        asset_name = a["asset_name"]

        asset = build_sftp_asset(
            asset_key=[code_location, "titan", asset_name],
            ssh_resource_key="ssh_titan",
            avro_schema=get_avro_record_schema(
                name=asset_name, fields=ASSET_FIELDS[asset_name]
            ),
            partitions_def=partitions_def,
            **a,
        )

        sftp_assets.append(asset)

    return sftp_assets
