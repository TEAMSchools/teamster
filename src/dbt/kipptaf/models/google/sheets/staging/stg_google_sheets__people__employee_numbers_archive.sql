select *,
from
    {{ source("google_sheets", "src_google_sheets__people__employee_numbers_archive") }}
