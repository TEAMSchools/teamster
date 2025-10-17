select *,
from {{ source("google_sheets", "src_google_sheets__kippfwd_expected_assessments") }}
