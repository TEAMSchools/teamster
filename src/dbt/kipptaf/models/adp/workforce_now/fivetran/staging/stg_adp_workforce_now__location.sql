select *, from {{ source("adp_workforce_now", "location") }}
