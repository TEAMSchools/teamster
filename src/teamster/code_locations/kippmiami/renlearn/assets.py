from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.renlearn.schema import (
    ACCELERATED_READER_SCHEMA,
    FAST_STAR_SCHEMA,
    STAR_DASHBOARD_STANDARDS_SCHEMA,
    STAR_SCHEMA,
    STAR_SKILL_AREA_SCHEMA,
)
from teamster.libraries.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_asset

asset_key_prefix = [CODE_LOCATION, "renlearn"]
remote_dir = "."
remote_file_regex = r"KIPP Miami\.zip"
ssh_resource_key = "ssh_renlearn"
slugify_cols = False

start_date_partition = FiscalYearPartitionsDefinition(
    start_date="2023-07-01", timezone=LOCAL_TIMEZONE.name, start_month=7
)

accelerated_reader = build_sftp_asset(
    asset_key=[*asset_key_prefix, "accelerated_reader"],
    remote_dir=remote_dir,
    remote_file_regex=remote_file_regex,
    archive_filepath=r"(?P<subject>)\.csv",
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

star = build_sftp_asset(
    asset_key=[*asset_key_prefix, "star"],
    remote_dir=remote_dir,
    remote_file_regex=remote_file_regex,
    archive_filepath=r"(?P<subject>)\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=STAR_SCHEMA,
    slugify_cols=slugify_cols,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR", "SEL"]),
            "start_date": start_date_partition,
        }
    ),
)

star_skill_area = build_sftp_asset(
    asset_key=[*asset_key_prefix, "star_skill_area"],
    remote_dir=remote_dir,
    remote_file_regex=remote_file_regex,
    archive_filepath=r"(?P<subject>)_SkillArea_v1\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=STAR_SKILL_AREA_SCHEMA,
    slugify_cols=slugify_cols,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR", "SEL"]),
            "start_date": start_date_partition,
        }
    ),
)

star_dashboard_standards = build_sftp_asset(
    asset_key=[*asset_key_prefix, "star_dashboard_standards"],
    remote_dir=remote_dir,
    remote_file_regex=remote_file_regex,
    archive_filepath=r"(?P<subject>)_Dashboard_Standards_v2\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=STAR_DASHBOARD_STANDARDS_SCHEMA,
    slugify_cols=slugify_cols,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR", "SEL"]),
            "start_date": start_date_partition,
        }
    ),
)

fast_star = build_sftp_asset(
    asset_key=[*asset_key_prefix, "fast_star"],
    remote_dir=remote_dir,
    remote_file_regex=remote_file_regex,
    archive_filepath=r"FL_FAST_(?P<subject>)_K-2\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=FAST_STAR_SCHEMA,
    slugify_cols=slugify_cols,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR", "SEL", "SEL_Domains"]),
            "start_date": start_date_partition,
        }
    ),
)

assets = [
    accelerated_reader,
    fast_star,
    star_dashboard_standards,
    star_skill_area,
    star,
]
