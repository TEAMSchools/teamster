select rubric_key, indicator, `level`, label, points,
from {{ source("google_sheets", "src_google_sheets__kfwd__career_launch_rubric") }}
where rubric_key is not null
