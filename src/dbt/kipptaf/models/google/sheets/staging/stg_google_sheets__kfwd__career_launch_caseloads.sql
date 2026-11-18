select advisor_name,
from {{ source("google_sheets", "src_google_sheets__kfwd__career_launch_caseloads") }}
where advisor_name is not null
