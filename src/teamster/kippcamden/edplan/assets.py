from dagster import AutoMaterializePolicy, DailyPartitionsDefinition

from teamster.core.sftp.assets import build_sftp_asset
from teamster.edplan.schema import NJSMART_POWERSCHOOL
from teamster.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE

njsmart_powerschool = build_sftp_asset(
    asset_key=[CODE_LOCATION, "edplan", "njsmart_powerschool"],
    remote_dir="Reports",
    remote_file_regex=r"NJSMART-Power[Ss]chool\.txt",
    ssh_resource_key="ssh_edplan",
    avro_schema=NJSMART_POWERSCHOOL,
    partitions_def=DailyPartitionsDefinition(
        start_date="2023-05-08",
        timezone=LOCAL_TIMEZONE.name,
        fmt="%Y-%m-%d",
        end_offset=1,
    ),
    auto_materialize_policy=AutoMaterializePolicy.eager(),
)

assets = [
    njsmart_powerschool,
]
