from teamster.code_locations.kippcamden import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kippcamden.titan.schema import PERSON_DATA_SCHEMA
from teamster.libraries.titan.assets import build_titan_sftp_asset

person_data = build_titan_sftp_asset(
    key=[CODE_LOCATION, "titan", "person_data"],
    remote_file_regex=r"Person Data(?P<fiscal_year>\d{4})\.csv",
    schema=PERSON_DATA_SCHEMA,
    partition_start_date="2020-07-01",
    timezone=LOCAL_TIMEZONE,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

assets = [
    person_data,
]
