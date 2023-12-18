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

njsmart_powerschool_archive = build_sftp_asset(
    asset_key=[CODE_LOCATION, "edplan", "njsmart_powerschool_archive"],
    remote_dir=f"/teamster-{CODE_LOCATION}/couchdrop/edplan/njsmart_powerschool_archive",
    remote_file_regex=r"src_edplan__njsmart_powerschool_archive\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=get_avro_record_schema(
        name="njsmart_powerschool_archive",
        fields=ASSET_FIELDS["njsmart_powerschool_archive"],
    ),
)

_all = [
    njsmart_powerschool,
    njsmart_powerschool_archive,
]
