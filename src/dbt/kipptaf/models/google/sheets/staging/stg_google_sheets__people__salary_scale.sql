select
    *,

    scale_ny_salary + 0.01 as scale_ny_salary_plus_1_cent,
    scale_cy_salary + 1 as scale_ny_salary_plus_1_dollar,
    scale_cy_salary - 1 as scale_ny_salary_minus_1_dollar,
from {{ source("google_sheets", "src_google_sheets__people__salary_scale") }}
