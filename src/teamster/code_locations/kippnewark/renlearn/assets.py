from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.renlearn.schema import (
    STAR_SCHEMA,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_archive_asset

star = build_sftp_archive_asset(
    asset_key=[CODE_LOCATION, "renlearn", "star"],
    remote_dir_regex=r"\.",
    remote_file_regex=r"KIPP TEAM & Family\.zip",
    archive_file_regex=r"(?P<subject>)\.csv",
    ssh_resource_key="ssh_renlearn",
    slugify_cols=False,
    avro_schema=STAR_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR"]),
            "start_date": FiscalYearPartitionsDefinition(
                start_date="2023-07-01", timezone=str(LOCAL_TIMEZONE), start_month=7
            ),
        }
    ),
)

assets = [
    star,
]
