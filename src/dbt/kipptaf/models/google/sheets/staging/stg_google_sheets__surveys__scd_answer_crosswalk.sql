select *,
from {{ source("google_sheets", "src_google_sheets__surveys__scd_answer_crosswalk") }}
