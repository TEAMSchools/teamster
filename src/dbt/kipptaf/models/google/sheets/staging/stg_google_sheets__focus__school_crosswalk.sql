select *,
from {{ source("google_sheets", "src_google_sheets__focus__school_crosswalk") }}
where finalsite_assigned_school is not null
