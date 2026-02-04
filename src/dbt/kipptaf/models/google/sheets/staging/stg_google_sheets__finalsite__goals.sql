select * except (academic_year),
from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
