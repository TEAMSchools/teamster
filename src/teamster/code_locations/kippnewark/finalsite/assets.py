from teamster.code_locations.kippnewark import CODE_LOCATION
from teamster.code_locations.kippnewark.finalsite.schema import (
    CONTACT_SCHEMA,
    CONTACT_STATUS_SCHEMA,
    FIELD_SCHEMA,
    GRADE_SCHEMA,
    SCHOOL_YEAR_SCHEMA,
    STATUS_REPORT_SCHEMA,
    USER_SCHEMA,
)
from teamster.libraries.finalsite.assets import build_finalsite_asset
from teamster.libraries.sftp.assets import build_sftp_folder_asset

status_report = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "finalsite", "status_report"],
    remote_dir_regex=rf"/data-team/{CODE_LOCATION}/finalsite/status_report",
    remote_file_regex=r".+\.csv",
    ssh_resource_key="ssh_couchdrop",
    avro_schema=STATUS_REPORT_SCHEMA,
)

contacts = build_finalsite_asset(
    code_location=CODE_LOCATION, asset_name="contacts", schema=CONTACT_SCHEMA
)

contact_statuses = build_finalsite_asset(
    code_location=CODE_LOCATION,
    asset_name="contact_statuses",
    schema=CONTACT_STATUS_SCHEMA,
)

fields = build_finalsite_asset(
    code_location=CODE_LOCATION, asset_name="fields", schema=FIELD_SCHEMA
)

grades = build_finalsite_asset(
    code_location=CODE_LOCATION, asset_name="grades", schema=GRADE_SCHEMA
)

school_years = build_finalsite_asset(
    code_location=CODE_LOCATION, asset_name="school_years", schema=SCHOOL_YEAR_SCHEMA
)

users = build_finalsite_asset(
    code_location=CODE_LOCATION, asset_name="users", schema=USER_SCHEMA
)

assets = [
    contact_statuses,
    contacts,
    fields,
    grades,
    school_years,
    status_report,
    users,
]
