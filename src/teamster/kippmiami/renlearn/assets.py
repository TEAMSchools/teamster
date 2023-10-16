from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.renlearn.schema import ASSET_FIELDS
from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.core.utils.functions import get_avro_record_schema

from .. import CODE_LOCATION, LOCAL_TIMEZONE

__all__ = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "renlearn", a["asset_name"]],
        ssh_resource_key="ssh_renlearn",
        avro_schema=get_avro_record_schema(
            name=a["asset_name"], fields=ASSET_FIELDS[a["asset_name"]]
        ),
        slugify_cols=False,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(a["partition_keys"]["subject"]),
                "start_date": FiscalYearPartitionsDefinition(
                    start_date=a["partition_keys"]["start_date"],
                    timezone=LOCAL_TIMEZONE.name,
                    start_month=7,
                ),
            }
        ),
        **a,
    )
    for a in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/renlearn/config/assets.yaml"]
    )["assets"]
]
