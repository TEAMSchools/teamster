select
    associate_id,
    membership_code,
    membership_description,
    category_code,
    category_description,

    parse_date('%m/%d/%Y', effective_date) as effective_date,
    parse_date('%m/%d/%Y', expiration_date) as expiration_date,
from {{ source("adp_workforce_now", "src_adp_workforce_now__employee_memberships") }}
