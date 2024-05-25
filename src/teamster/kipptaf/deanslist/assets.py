from teamster.core.sftp.assets import build_sftp_asset
from teamster.kipptaf.deanslist.schema import (
    RECONCILE_ATTENDANCE_SCHEMA,
    RECONCILE_SUSPENSIONS_SCHEMA,
)

reconcile_attendance = build_sftp_asset(
    asset_key=["deanslist", "reconcile_attendance"],
    remote_dir="reconcile_report_files",
    remote_file_regex=r"ktaf_reconcile_att\.csv",
    ssh_resource_key="ssh_deanslist",
    avro_schema=RECONCILE_ATTENDANCE_SCHEMA,
)

reconcile_suspensions = build_sftp_asset(
    asset_key=["deanslist", "reconcile_suspensions"],
    remote_dir="reconcile_report_files",
    remote_file_regex=r"ktaf_reconcile_susp\.csv",
    ssh_resource_key="ssh_deanslist",
    avro_schema=RECONCILE_SUSPENSIONS_SCHEMA,
)

assets = [
    reconcile_attendance,
    reconcile_suspensions,
]
