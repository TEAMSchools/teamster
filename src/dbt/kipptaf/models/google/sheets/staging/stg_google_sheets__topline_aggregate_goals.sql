select *,
from {{ source("google_sheets", "src_google_sheets__topline_aggregate_goals") }}
