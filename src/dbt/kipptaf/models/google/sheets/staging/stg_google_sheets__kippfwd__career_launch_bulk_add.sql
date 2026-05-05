select
    contact_id,
    email,
    cell_phone,
    education_level,
    post_grad_plan,
    salary,
    company,

    cast(job_satisfaction as string) as job_satisfaction,
    cast(benefits as string) as benefits,
from {{ source("google_sheets", "src_google_sheets__kippfwd__career_launch_bulk_add") }}
