select *,
from {{ source("google_sheets", "src_google_sheets__kippfwd_act_scale_score_key") }}
