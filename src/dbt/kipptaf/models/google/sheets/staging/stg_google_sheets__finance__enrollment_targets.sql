select *, fiscal_year - 1 as academic_year,
from {{ source("google_sheets", "src_google_sheets__finance__enrollment_targets") }}
where fiscal_year is not null
