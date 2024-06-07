from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.deanslist.schema import (
    RECONCILE_ATTENDANCE_SCHEMA,
    RECONCILE_SUSPENSIONS_SCHEMA,
)
from teamster.libraries.sftp.assets import build_sftp_asset

reconcile_attendance = build_sftp_asset(
    asset_key=[CODE_LOCATION, "deanslist", "reconcile_attendance"],
    remote_dir="reconcile_report_files",
    remote_file_regex=r"ktaf_reconcile_att\.csv",
    ssh_resource_key="ssh_deanslist",
    avro_schema=RECONCILE_ATTENDANCE_SCHEMA,
)

reconcile_suspensions = build_sftp_asset(
    asset_key=[CODE_LOCATION, "deanslist", "reconcile_suspensions"],
    remote_dir="reconcile_report_files",
    remote_file_regex=r"ktaf_reconcile_susp\.csv",
    ssh_resource_key="ssh_deanslist",
    avro_schema=RECONCILE_SUSPENSIONS_SCHEMA,
)

assets = [
    reconcile_attendance,
    reconcile_suspensions,
]
