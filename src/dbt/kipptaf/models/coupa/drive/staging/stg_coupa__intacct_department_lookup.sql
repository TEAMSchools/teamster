select *, from {{ source("coupa", "src_coupa__intacct_department_lookup") }}
