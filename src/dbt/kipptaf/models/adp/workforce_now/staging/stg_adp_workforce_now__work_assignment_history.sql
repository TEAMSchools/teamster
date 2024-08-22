select *, from {{ source("adp_workforce_now", "work_assignment_history") }}
