select *,
from
    {{ source("google_sheets", "src_google_sheets__focus__enrollment_code_crosswalk") }}
where finalsite_lifecycle_action is not null
