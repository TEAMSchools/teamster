-- depends_on: {{ ref("stg_google_sheets__people__location_crosswalk") }}
select `Name`, count(*) as n_rows,
from {{ source("google_sheets", "src_google_sheets__people__location_crosswalk") }}
group by `Name`
having count(*) > 1
