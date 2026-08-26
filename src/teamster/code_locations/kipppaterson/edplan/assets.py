from dagster import AutomationCondition, DailyPartitionsDefinition

from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipppaterson.edplan.schema import (
    NJSMART_POWERSCHOOL_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

njsmart_powerschool = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "edplan", "njsmart_powerschool"],
    remote_dir_regex=r"Reports",
    # Paterson's EdPlan account exports this report instead of Newark's and
    # Camden's `NJSMART-PowerSchool.txt`. Same 37 columns, same comma delimiter;
    # only the file name differs, and it carries the export date. The named
    # group resolves to the partition key, so exactly one file matches per
    # partition -- the file's mtime date equals the date in its name.
    remote_file_regex=(
        r"EDPlan Special Education Data Export-PCG Support-(?P<date>[\d-]+)\.txt"
    ),
    ssh_resource_key="ssh_edplan",
    avro_schema=NJSMART_POWERSCHOOL_SCHEMA,
    partitions_def=DailyPartitionsDefinition(
        # First file EdPlan produced for Paterson.
        start_date="2026-08-24",
        timezone=str(LOCAL_TIMEZONE),
        fmt="%Y-%m-%d",
        end_offset=1,
    ),
    automation_condition=AutomationCondition.eager(),
)

assets = [
    njsmart_powerschool,
]
