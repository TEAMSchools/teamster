select max(file_year) as academic_year,
from {{ ref("stg_google_sheets__finalsite__status_crosswalk") }}
