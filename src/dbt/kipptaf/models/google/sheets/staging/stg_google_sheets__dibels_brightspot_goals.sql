select *,
from {{ source("google_sheets", "src_google_sheets__dibels__brightspot_goals") }}
