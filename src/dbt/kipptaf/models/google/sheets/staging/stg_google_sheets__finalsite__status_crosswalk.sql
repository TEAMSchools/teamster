select *,
from {{ source("google_sheets", "src_google_sheets__finalsite__status_crosswalk") }}
