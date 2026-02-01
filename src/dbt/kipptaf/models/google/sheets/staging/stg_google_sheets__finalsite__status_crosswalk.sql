select * except (academic_year), academic_year as sre_academic_year,
from {{ source("google_sheets", "src_google_sheets__finalsite__status_crosswalk") }}
