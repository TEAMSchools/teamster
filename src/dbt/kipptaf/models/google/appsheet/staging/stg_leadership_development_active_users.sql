select * except (employee_number), safe_cast(employee_number as int) as employee_number,
from {{ source("google_appsheet", "src_leadership_development_active_users") }}
