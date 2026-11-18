-- depends_on: {{ ref("stg_google_sheets__people__powerschool_crosswalk") }}
select employee_number, count(*) as n_active_rows,
from {{ source("google_sheets", "src_google_sheets__people__powerschool_crosswalk") }}
where is_active and employee_number is not null
group by employee_number
having count(*) > 1
