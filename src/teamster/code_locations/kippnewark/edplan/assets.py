from dagster import AutomationCondition, DailyPartitionsDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.edplan.schema import NJSMART_POWERSCHOOL_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_file_asset

njsmart_powerschool = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "edplan", "njsmart_powerschool"],
    remote_dir_regex=r"Reports",
    remote_file_regex=r"NJSMART-Power[Ss]chool\.txt",
    ssh_resource_key="ssh_edplan",
    avro_schema=NJSMART_POWERSCHOOL_SCHEMA,
    partitions_def=DailyPartitionsDefinition(
        start_date="2023-05-08",
        timezone=str(LOCAL_TIMEZONE),
        fmt="%Y-%m-%d",
        end_offset=1,
    ),
    automation_condition=AutomationCondition.eager(),
)

assets = [
    njsmart_powerschool,
]
