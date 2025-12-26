select *,
from {{ source("google_sheets", "src_google_sheets__finalsite_status_crosswalk") }}
