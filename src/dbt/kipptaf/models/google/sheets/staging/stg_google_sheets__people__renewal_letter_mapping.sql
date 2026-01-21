select *,
from {{ source("google_sheets", "src_google_sheets__people__renewal_letter_mapping") }}
