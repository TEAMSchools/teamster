select *,
from {{ source("google_sheets", "src_google_sheets__people__campus_crosswalk") }}
