select string_field_0 as finalsite_student_id,
from {{ source("google_sheets", "src_google_sheets__finalsite__exclude_ids") }}
