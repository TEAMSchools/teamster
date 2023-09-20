select * from {{ source("dayforce", "src_dayforce__employee_manager") }}
