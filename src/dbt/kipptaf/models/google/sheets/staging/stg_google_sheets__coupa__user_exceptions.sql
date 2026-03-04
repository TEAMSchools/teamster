select *,
from {{ source("google_sheets", "src_google_sheets__coupa__user_exceptions") }}
