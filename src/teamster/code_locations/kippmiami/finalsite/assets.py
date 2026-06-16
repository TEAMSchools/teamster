from teamster.code_locations.kippmiami import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippmiami.finalsite.schema import (
    CONTACTS_SCHEMA,
    STATUS_REPORT_SCHEMA,
)
from teamster.libraries.finalsite.api.assets import build_finalsite_contacts_asset
from teamster.libraries.finalsite.sftp.assets import (
    get_finalsite_school_year_partition_keys,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

status_report = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "finalsite", "status_report"],
    remote_dir_regex=rf"/data-team/{CODE_LOCATION}/finalsite/status_report",
    remote_file_regex=(
        rf"{CODE_LOCATION}_SwissArmyExport_SFTP_Export___"
        r"Status_Report_SFTP_Status_Export___"
        r"(?P<school_year>\d+_\d+)\.csv"
    ),
    partitions_def=get_finalsite_school_year_partition_keys(
        start_year=2025, end_year=CURRENT_FISCAL_YEAR.fiscal_year
    ),
    avro_schema=STATUS_REPORT_SCHEMA,
    ssh_resource_key="ssh_couchdrop",
)

contacts = build_finalsite_contacts_asset(
    code_location=CODE_LOCATION, schema=CONTACTS_SCHEMA
)

assets = [
    status_report,
    contacts,
]
