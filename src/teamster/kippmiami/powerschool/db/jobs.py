from dagster import AssetSelection, HourlyPartitionsDefinition, define_asset_job

from teamster.core.utils.variables import LOCAL_TIME_ZONE

from ... import POWERSCHOOL_PARTITION_START_DATE
from .assets import ps_db_assets, ps_db_partitioned_assets

ps_db_asset_job = define_asset_job(
    name="ps_db_asset_job",
    selection=AssetSelection.assets(*ps_db_assets),
)

ps_db_partitioned_asset_job = define_asset_job(
    name="ps_db_partitioned_asset_job",
    selection=AssetSelection.assets(*ps_db_partitioned_assets),
    partitions_def=HourlyPartitionsDefinition(
        start_date=POWERSCHOOL_PARTITION_START_DATE,
        timezone=str(LOCAL_TIME_ZONE),
        fmt="%Y-%m-%dT%H:%M:%S.%f%z",
    ),
)

__all__ = [ps_db_asset_job, ps_db_partitioned_asset_job]
