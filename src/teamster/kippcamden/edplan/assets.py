from dagster import AutoMaterializePolicy, DailyPartitionsDefinition

from teamster.core.edplan.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.functions import get_avro_record_schema

from .. import CODE_LOCATION, LOCAL_TIMEZONE

njsmart_powerschool = build_sftp_asset(
    asset_key=[CODE_LOCATION, "edplan", "njsmart_powerschool"],
    remote_dir="Reports",
    remote_file_regex=r"NJSMART-Power[Ss]chool\.txt",
    ssh_resource_key="ssh_edplan",
    avro_schema=get_avro_record_schema(
        name="njsmart_powerschool", fields=ASSET_FIELDS["njsmart_powerschool"]
    ),
    partitions_def=DailyPartitionsDefinition(
        start_date="2023-05-08",
        timezone=LOCAL_TIMEZONE.name,
        fmt="%Y-%m-%d",
        end_offset=1,
    ),
    auto_materialize_policy=AutoMaterializePolicy.eager(),
)

_all = [
    njsmart_powerschool,
]
