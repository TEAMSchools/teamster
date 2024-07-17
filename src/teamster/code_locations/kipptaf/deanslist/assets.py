from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.deanslist.schema import (
    RECONCILE_ATTENDANCE_SCHEMA,
    RECONCILE_SUSPENSIONS_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

remote_dir_regex = r"reconcile_report_files"
ssh_resource_key = "ssh_deanslist"
key_prefix = [CODE_LOCATION, "deanslist"]

reconcile_attendance = build_sftp_file_asset(
    asset_key=[*key_prefix, "reconcile_attendance"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=r"ktaf_reconcile_att\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=RECONCILE_ATTENDANCE_SCHEMA,
)

reconcile_suspensions = build_sftp_file_asset(
    asset_key=[*key_prefix, "reconcile_suspensions"],
    remote_dir_regex=remote_dir_regex,
    remote_file_regex=r"ktaf_reconcile_susp\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=RECONCILE_SUSPENSIONS_SCHEMA,
)

assets = [
    reconcile_attendance,
    reconcile_suspensions,
]
