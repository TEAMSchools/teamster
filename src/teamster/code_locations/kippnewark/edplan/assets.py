from dagster import AutomationCondition, DailyPartitionsDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.edplan.schema import (
    NJSMART_POWERSCHOOL_SCHEMA,
    SECTION_504_STUDENT_REPORT_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

# Shared by both assets: the EdPlan sensor runs them in one job, and a job
# rejects assets with different partitions definitions.
partitions_def = DailyPartitionsDefinition(
    start_date="2023-05-08",
    timezone=str(LOCAL_TIMEZONE),
    fmt="%Y-%m-%d",
    end_offset=1,
)

njsmart_powerschool = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "edplan", "njsmart_powerschool"],
    remote_dir_regex=r"Reports",
    remote_file_regex=r"NJSMART-Power[Ss]chool\.txt",
    ssh_resource_key="ssh_edplan",
    avro_schema=NJSMART_POWERSCHOOL_SCHEMA,
    partitions_def=partitions_def,
    automation_condition=AutomationCondition.eager(),
)

section_504_student_report = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "edplan", "section_504_student_report"],
    remote_dir_regex=r"Reports",
    remote_file_regex=r"EDPlan-504StudentReport\.csv",
    ssh_resource_key="ssh_edplan",
    avro_schema=SECTION_504_STUDENT_REPORT_SCHEMA,
    partitions_def=partitions_def,
    # "504_case_manager" would start with a digit, which Avro rejects
    slugify_replacements=[["504 Case Manager", "Section 504 Case Manager"]],
    automation_condition=AutomationCondition.eager(),
)

assets = [
    njsmart_powerschool,
    section_504_student_report,
]
