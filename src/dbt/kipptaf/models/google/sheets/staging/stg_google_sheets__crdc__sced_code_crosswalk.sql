select *,
from {{ source("google_sheets", "src_google_sheets__crdc__sced_code_crosswalk") }}
