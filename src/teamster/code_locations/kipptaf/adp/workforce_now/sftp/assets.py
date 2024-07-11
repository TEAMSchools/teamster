from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.adp.workforce_now.sftp.schema import (
    ADDITIONAL_EARNINGS_REPORT_SCHEMA,
    COMPREHENSIVE_BENEFITS_REPORT_SCHEMA,
    PENSION_AND_BENEFITS_ENROLLMENTS_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

remote_dir_regex = r"\."
ssh_resource_key = "ssh_adp_workforce_now"
key_prefix = [CODE_LOCATION, "adp", "workforce_now"]

pension_and_benefits_enrollments = build_sftp_file_asset(
    asset_key=[*key_prefix, "pension_and_benefits_enrollments"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=r"pension_and_benefits_enrollments\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=PENSION_AND_BENEFITS_ENROLLMENTS_SCHEMA,
    exclude_dirs=["./payroll"],
)

comprehensive_benefits_report = build_sftp_file_asset(
    asset_key=[*key_prefix, "comprehensive_benefits_report"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=r"comprehensive_benefits_report\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=COMPREHENSIVE_BENEFITS_REPORT_SCHEMA,
    exclude_dirs=["./payroll"],
)

additional_earnings_report = build_sftp_file_asset(
    asset_key=[*key_prefix, "additional_earnings_report"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=r"additional_earnings_report\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=ADDITIONAL_EARNINGS_REPORT_SCHEMA,
    exclude_dirs=["./payroll"],
)

assets = [
    additional_earnings_report,
    comprehensive_benefits_report,
    pension_and_benefits_enrollments,
]
