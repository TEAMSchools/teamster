select *, from {{ source("adp_workforce_now", "person_military_classification") }}
