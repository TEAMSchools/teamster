from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.code_locations.kippmiami.finalsite.schema import STATUS_REPORT_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_folder_asset

status_report = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "finalsite", "status_report"],
    remote_dir_regex=rf"/data-team/{CODE_LOCATION}/finalsite/status_report",
    remote_file_regex=r".+\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=STATUS_REPORT_SCHEMA,
)

assets = [
    status_report,
]
