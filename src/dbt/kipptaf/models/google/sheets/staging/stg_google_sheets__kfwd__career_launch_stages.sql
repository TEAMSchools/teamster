select stage_key, stage, min_score,
from {{ source("google_sheets", "src_google_sheets__kfwd__career_launch_stages") }}
where stage_key is not null
