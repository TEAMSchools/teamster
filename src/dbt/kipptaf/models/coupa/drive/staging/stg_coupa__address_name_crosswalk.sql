select *, from {{ source("coupa", "src_coupa__address_name_crosswalk") }}
