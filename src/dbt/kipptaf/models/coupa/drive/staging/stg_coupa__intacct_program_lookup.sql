select
    adp_business_unit_home_code,
    adp_home_work_location_name,
    sage_intacct_program,
    sage_intacct_location,
from {{ source("coupa", "src_coupa__intacct_program_lookup") }}
