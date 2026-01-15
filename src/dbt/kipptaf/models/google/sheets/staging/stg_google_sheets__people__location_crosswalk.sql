select *,
from {{ source("google_sheets", "src_google_sheets__people__location_crosswalk") }}
