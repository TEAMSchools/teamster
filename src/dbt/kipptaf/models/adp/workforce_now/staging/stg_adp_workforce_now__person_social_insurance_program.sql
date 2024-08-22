select *, from {{ source("adp_workforce_now", "person_social_insurance_program") }}
