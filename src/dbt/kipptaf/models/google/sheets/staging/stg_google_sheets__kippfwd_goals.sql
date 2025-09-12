select *, from {{ source("google_sheets", "src_google_sheets__kippfwd_goals") }}
