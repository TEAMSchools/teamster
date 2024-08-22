select *, from {{ source("adp_workforce_now", "groups") }}
