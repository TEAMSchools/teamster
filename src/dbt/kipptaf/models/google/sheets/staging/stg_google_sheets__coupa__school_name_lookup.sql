select *,
from {{ source("google_sheets", "src_google_sheets__coupa__school_name_lookup") }}
