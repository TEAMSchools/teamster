select
    id, active, purchasing_user, safe_cast(employee_number as int) as employee_number,
from {{ source("coupa", "src_coupa__users") }}
