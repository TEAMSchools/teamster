import pathlib

from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.sftp.assets import build_sftp_asset
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.kippmiami import LOCAL_TIMEZONE
from teamster.kippmiami.renlearn.schema import ASSET_SCHEMA

assets = [
    build_sftp_asset(
        asset_key=["renlearn", a["asset_name"]],
        ssh_resource_key="ssh_renlearn",
        avro_schema=ASSET_SCHEMA[a["asset_name"]],
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
        [f"{pathlib.Path(__file__).parent}/config/assets.yaml"],
    )["assets"]
]
