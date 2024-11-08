from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.renlearn.schema import (
    ACCELERATED_READER_SCHEMA,
    STAR_SCHEMA,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_archive_asset

asset_key_prefix = [CODE_LOCATION, "renlearn"]
remote_dir_regex = r"\."
remote_file_regex = r"KIPP TEAM & Family\.zip"
archive_file_regex = r"(?P<subject>)\.csv"
ssh_resource_key = "ssh_renlearn"
slugify_cols = False

start_date_partition = FiscalYearPartitionsDefinition(
    start_date="2023-07-01", timezone=LOCAL_TIMEZONE.name, start_month=7
)

accelerated_reader = build_sftp_archive_asset(
    asset_key=[*asset_key_prefix, "accelerated_reader"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=remote_file_regex,
    archive_file_regex=archive_file_regex,
    ssh_resource_key=ssh_resource_key,
    avro_schema=ACCELERATED_READER_SCHEMA,
    slugify_cols=slugify_cols,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["AR"]),
            "start_date": start_date_partition,
        }
    ),
)

star = build_sftp_archive_asset(
    asset_key=[*asset_key_prefix, "star"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=remote_file_regex,
    archive_file_regex=archive_file_regex,
    ssh_resource_key=ssh_resource_key,
    avro_schema=STAR_SCHEMA,
    slugify_cols=slugify_cols,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR"]),
            "start_date": start_date_partition,
        }
    ),
)

assets = [
    accelerated_reader,
    star,
]
