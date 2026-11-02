select band_key, label, min_gpa, points,
from {{ source("google_sheets", "src_google_sheets__kfwd__career_launch_gpa_bands") }}
where band_key is not null
