select *, from {{ source("coupa", "src_coupa__user_exceptions") }}
