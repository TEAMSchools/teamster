select *,
from {{ source("google_sheets", "src_google_sheets__assessments__academic_goals") }}
