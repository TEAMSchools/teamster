select count(distinct file_year) as distinct_file_years,
from {{ ref("stg_google_sheets__finalsite__status_crosswalk") }}
having count(distinct file_year) != 1
