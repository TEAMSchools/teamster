select *, from {{ source("adp_workforce_now", "worker_group") }}
