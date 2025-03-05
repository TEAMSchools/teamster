select *, from {{ source("coupa", "src_coupa__intacct_fund_lookup") }}
