select *,
from {{ source("google_sheets", "src_google_sheets__focus__language_code_crosswalk") }}
where finalsite_language is not null
