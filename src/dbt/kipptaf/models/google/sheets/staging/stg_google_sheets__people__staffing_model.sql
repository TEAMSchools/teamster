select *,
from {{ source("google_sheets", "src_google_sheets__people__staffing_model") }}
