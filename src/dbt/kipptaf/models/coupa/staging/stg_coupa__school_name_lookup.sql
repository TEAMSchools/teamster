select *, from {{ source("coupa", "src_coupa__school_name_lookup") }}
