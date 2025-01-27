select *, from {{ source("coupa", "src_coupa__intacct_program_lookup") }}
