from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.renlearn.schema import (
    FAST_STAR_SCHEMA,
    STAR_DASHBOARD_STANDARDS_SCHEMA,
    STAR_SCHEMA,
    STAR_SKILL_AREA_SCHEMA,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_archive_asset

asset_key_prefix = [CODE_LOCATION, "renlearn"]
asset_kwargs = {
    "remote_dir_regex": r"\.",
    "remote_file_regex": r"KIPP Miami\.zip",
    "ssh_resource_key": "ssh_renlearn",
    "slugify_cols": False,
}

start_date_partition = FiscalYearPartitionsDefinition(
    start_date="2023-07-01", timezone=str(LOCAL_TIMEZONE), start_month=7
)

star = build_sftp_archive_asset(
    asset_key=[*asset_key_prefix, "star"],
    archive_file_regex=r"(?P<subject>)\.csv",
    avro_schema=STAR_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR", "SEL"]),
            "start_date": start_date_partition,
        }
    ),
    **asset_kwargs,
)

star_skill_area = build_sftp_archive_asset(
    asset_key=[*asset_key_prefix, "star_skill_area"],
    archive_file_regex=r"(?P<subject>)_SkillArea_v1\.csv",
    avro_schema=STAR_SKILL_AREA_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR", "SEL"]),
            "start_date": start_date_partition,
        }
    ),
    **asset_kwargs,
)

star_dashboard_standards = build_sftp_archive_asset(
    asset_key=[*asset_key_prefix, "star_dashboard_standards"],
    archive_file_regex=r"(?P<subject>)_Dashboard_Standards_v2\.csv",
    avro_schema=STAR_DASHBOARD_STANDARDS_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR", "SEL"]),
            "start_date": start_date_partition,
        }
    ),
    **asset_kwargs,
)

fast_star = build_sftp_archive_asset(
    asset_key=[*asset_key_prefix, "fast_star"],
    archive_file_regex=r"FL_FAST_(?P<subject>)_K-2\.csv",
    avro_schema=FAST_STAR_SCHEMA,
    partitions_def=MultiPartitionsDefinition(
        {
            "subject": StaticPartitionsDefinition(["SM", "SR", "SEL", "SEL_Domains"]),
            "start_date": start_date_partition,
        }
    ),
    **asset_kwargs,
)

assets = [
    fast_star,
    star_dashboard_standards,
    star_skill_area,
    star,
]
