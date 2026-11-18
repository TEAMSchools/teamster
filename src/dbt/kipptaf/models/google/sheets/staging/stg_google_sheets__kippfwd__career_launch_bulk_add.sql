select
    contact_id,
    email,
    cell_phone,
    education_level,
    post_grad_plan,
    salary,
    job_satisfaction,
    company,
    benefits,
from {{ source("google_sheets", "src_google_sheets__kippfwd__career_launch_bulk_add") }}
where contact_id is not null
