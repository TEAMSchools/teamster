-- depends_on: {{ ref("stg_google_sheets__people__location_crosswalk") }}
select name, count(*) as n_rows,
from {{ source("google_sheets", "src_google_sheets__people__location_crosswalk") }}
where name is not null
group by name
having count(*) > 1
