select *,
from {{ source("google_sheets", "src_google_sheets__student_graduation_path_combos") }}
