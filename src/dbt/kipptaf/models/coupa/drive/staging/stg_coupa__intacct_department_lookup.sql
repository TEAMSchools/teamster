select
    adp_business_unit_home_code,
    adp_department_home_name,
    adp_job_title,
    sage_intacct_department,
from {{ source("coupa", "src_coupa__intacct_department_lookup") }}
