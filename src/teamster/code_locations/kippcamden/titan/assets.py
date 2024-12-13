from teamster.code_locations.kippcamden import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippcamden.titan.schema import PERSON_DATA_SCHEMA
from teamster.libraries.titan.assets import build_titan_sftp_asset

person_data = build_titan_sftp_asset(
    key=[CODE_LOCATION, "titan", "person_data"],
    remote_file_regex=r"[Pp]erson\s?[Dd]ata(?P<fiscal_year>\d{4})\.csv",
    schema=PERSON_DATA_SCHEMA,
    partition_start_date="2020-07-01",
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

assets = [
    person_data,
]
