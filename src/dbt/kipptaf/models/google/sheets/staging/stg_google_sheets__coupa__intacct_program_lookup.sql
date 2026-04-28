select
    adp_business_unit_home_code,
    sage_intacct_program,
    sage_intacct_location,

    adp_home_work_location_name as location_clean_name,
from {{ source("google_sheets", "src_google_sheets__coupa__intacct_program_lookup") }}
