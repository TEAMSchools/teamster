select * except (cutoff), cast(cutoff as numeric) as cutoff,
from {{ source("google_sheets", "src_google_sheets__topline_student_goals") }}
