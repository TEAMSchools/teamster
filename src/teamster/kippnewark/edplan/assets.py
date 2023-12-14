from dagster import AutoMaterializePolicy, DailyPartitionsDefinition, config_from_files

from teamster.core.edplan.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.functions import get_avro_record_schema

from .. import CODE_LOCATION, LOCAL_TIMEZONE

_all = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "edplan", a["asset_name"]],
        avro_schema=get_avro_record_schema(
            name=a["asset_name"], fields=ASSET_FIELDS[a["asset_name"]]
        ),
        ssh_resource_key="ssh_edplan",
        partitions_def=DailyPartitionsDefinition(
            start_date=a["partition_start_date"],
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%d",
            end_offset=1,
        ),
        auto_materialize_policy=AutoMaterializePolicy.eager(),
        **a,
    )
    for a in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/edplan/config/assets.yaml"]
    )["assets"]
]
