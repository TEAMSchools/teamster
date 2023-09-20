select * from {{ source("dayforce", "src_dayforce__employee_work_assignment") }}
