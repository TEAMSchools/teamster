select *, from {{ source("adp_workforce_now", "worker_assigned_location") }}
