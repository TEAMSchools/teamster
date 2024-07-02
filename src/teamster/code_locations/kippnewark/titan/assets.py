from teamster.code_locations.kippnewark import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippnewark.titan.schema import (
    INCOME_FORM_DATA_SCHEMA,
    PERSON_DATA_SCHEMA,
)
from teamster.libraries.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_asset

asset_key_prefix = [CODE_LOCATION, "titan"]
remote_dir = "."
ssh_resource_key = "ssh_titan"

person_data = build_sftp_asset(
    asset_key=[*asset_key_prefix, "person_data"],
    remote_dir=remote_dir,
    remote_file_regex=r"Person Data(?P<fiscal_year>\d{4})\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=PERSON_DATA_SCHEMA,
    partitions_def=FiscalYearPartitionsDefinition(
        start_date="2020-07-01", start_month=7, timezone=LOCAL_TIMEZONE.name, fmt="%Y"
    ),
)

income_form_data = build_sftp_asset(
    asset_key=[*asset_key_prefix, "income_form_data"],
    remote_dir=remote_dir,
    remote_file_regex=r"Income Form Data(?P<fiscal_year>\d{4})\.csv",
    ssh_resource_key=ssh_resource_key,
    avro_schema=INCOME_FORM_DATA_SCHEMA,
    partitions_def=FiscalYearPartitionsDefinition(
        start_date="2021-07-01", start_month=7, timezone=LOCAL_TIMEZONE.name, fmt="%Y"
    ),
)

assets = [
    income_form_data,
    person_data,
]
