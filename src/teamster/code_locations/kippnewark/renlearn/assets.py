import pathlib

from dagster import (
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.renlearn.schema import ASSET_SCHEMA
from teamster.libraries.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_asset

assets = [
    build_sftp_asset(
        asset_key=[CODE_LOCATION, "renlearn", a["asset_name"]],
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
