from teamster.code_locations.kippnewark import (
    CODE_LOCATION,
    CURRENT_FISCAL_YEAR,
    LOCAL_TIMEZONE,
)
from teamster.code_locations.kippnewark.titan.schema import (
    INCOME_FORM_DATA_SCHEMA,
    PERSON_DATA_SCHEMA,
)
from teamster.libraries.titan.assets import build_titan_sftp_asset

asset_key_prefix = [CODE_LOCATION, "titan"]

person_data = build_titan_sftp_asset(
    key=[*asset_key_prefix, "person_data"],
    remote_file_regex=r"[Pp]erson\s?[Dd]ata(?P<fiscal_year>\d{4})\.csv",
    schema=PERSON_DATA_SCHEMA,
    partition_start_date="2020-07-01",
    timezone=LOCAL_TIMEZONE,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

income_form_data = build_titan_sftp_asset(
    key=[*asset_key_prefix, "income_form_data"],
    remote_file_regex=r"[Ii]ncome\s?[Ff]orm\s?[Dd]ata(?P<fiscal_year>\d{4})\.csv",
    schema=INCOME_FORM_DATA_SCHEMA,
    partition_start_date="2021-07-01",
    timezone=LOCAL_TIMEZONE,
    current_fiscal_year=CURRENT_FISCAL_YEAR,
)

assets = [
    income_form_data,
    person_data,
]
