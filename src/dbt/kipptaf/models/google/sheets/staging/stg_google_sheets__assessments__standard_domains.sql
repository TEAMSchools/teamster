select *,
from {{ source("google_sheets", "src_google_sheets__assessments__standard_domains") }}
