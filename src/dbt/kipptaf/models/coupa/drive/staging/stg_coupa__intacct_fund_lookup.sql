select adp_business_unit_home_code, sage_intacct_fund,
from {{ source("coupa", "src_coupa__intacct_fund_lookup") }}
