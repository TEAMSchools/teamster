select *,
from {{ source("google_sheets", "src_google_sheets__focus__grade_crosswalk") }}
where finalsite_grade_canonical_name is not null
