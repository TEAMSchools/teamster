select
    id,
    active,
    purchasing_user,
    login,
    safe_cast(employee_number as int) as employee_number,
from {{ source("coupa", "src_coupa__users") }}
