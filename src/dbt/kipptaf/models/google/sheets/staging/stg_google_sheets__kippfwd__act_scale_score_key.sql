select *,
from {{ source("google_sheets", "src_google_sheets__kippfwd__act_scale_score_key") }}
