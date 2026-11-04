select * except (grade_level),
from {{ source("google_sheets", "src_google_sheets__gradebook_flags") }}
