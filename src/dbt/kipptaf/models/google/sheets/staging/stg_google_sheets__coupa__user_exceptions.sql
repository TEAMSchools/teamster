select
    employee_number,
    coupa_school_name,
    sage_intacct_department,

    home_work_location_name as location_clean_name,
from {{ source("google_sheets", "src_google_sheets__coupa__user_exceptions") }}
