select *,
from
    {{ source("google_sheets", "src_google_sheets__assessments__act_scale_score_key") }}
