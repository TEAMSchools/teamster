from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.adp.workforce_now.sftp.schema import (
    ADDITIONAL_EARNINGS_REPORT_SCHEMA,
    PENSION_AND_BENEFITS_ENROLLMENTS_SCHEMA,
    TIME_AND_ATTENDANCE_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

key_prefix = [CODE_LOCATION, "adp", "workforce_now", "sftp"]
asset_kwargs = {
    "remote_dir_regex": r"\.",
    "ssh_resource_key": "ssh_adp_workforce_now",
    "group_name": "adp_workforce_now",
    "exclude_dirs": [r"\./payroll"],
}

pension_and_benefits_enrollments = build_sftp_file_asset(
    asset_key=[*key_prefix, "pension_and_benefits_enrollments"],
    remote_file_regex=r"pension_and_benefits_enrollments\.csv",
    avro_schema=PENSION_AND_BENEFITS_ENROLLMENTS_SCHEMA,
    **asset_kwargs,
)

additional_earnings_report = build_sftp_file_asset(
    asset_key=[*key_prefix, "additional_earnings_report"],
    remote_file_regex=r"additional_earnings_report\.csv",
    avro_schema=ADDITIONAL_EARNINGS_REPORT_SCHEMA,
    **asset_kwargs,
)

time_and_attendance = build_sftp_file_asset(
    asset_key=[*key_prefix, "time_and_attendance"],
    remote_file_regex=r"adp__wfn__employment_profile__time_and_attendance\.csv",
    avro_schema=TIME_AND_ATTENDANCE_SCHEMA,
    **asset_kwargs,
)

assets = [
    additional_earnings_report,
    pension_and_benefits_enrollments,
    time_and_attendance,
]
