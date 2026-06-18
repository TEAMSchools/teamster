select *,
from {{ source("google_sheets", "src_google_sheets__focus__drop_code_crosswalk") }}
where finalsite_withdrawal_reason is not null
