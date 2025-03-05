select *, from {{ source("coupa", "src_coupa__intacct_location_lookup") }}
