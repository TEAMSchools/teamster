import pendulum
from dagster import StaticPartitionsDefinition, config_from_files

from teamster.core.pearson.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.classes import FiscalYear


def build_pearson_sftp_assets(config_dir, code_location, timezone, max_fiscal_year):
    sftp_assets = []

    for a in config_from_files([f"{config_dir}/assets.yaml"])["assets"]:
        start_fy = FiscalYear(
            datetime=pendulum.from_format(
                string=a["partition_start_date"], fmt="YYYY-MM-DD", tz=timezone
            ),
            start_month=7,
        )

        partitions_def = StaticPartitionsDefinition(
            [str(fy)[-2:] for fy in range(start_fy.fiscal_year, max_fiscal_year)]
        )

        asset = build_sftp_asset(
            code_location=code_location,
            source_system="pearson",
            asset_fields=ASSET_FIELDS,
            ssh_resource_key="ssh_couchdrop",
            partitions_def=partitions_def,
            **a,
        )

        sftp_assets.append(asset)

    return sftp_assets
