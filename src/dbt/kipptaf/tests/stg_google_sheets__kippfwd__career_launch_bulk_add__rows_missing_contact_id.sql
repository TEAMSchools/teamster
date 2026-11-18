-- depends_on: {{ ref("stg_google_sheets__kippfwd__career_launch_bulk_add") }}
select email, cell_phone, company,
from {{ source("google_sheets", "src_google_sheets__kippfwd__career_launch_bulk_add") }}
where
    contact_id is null
    and coalesce(
        email,
        cell_phone,
        education_level,
        post_grad_plan,
        salary,
        job_satisfaction,
        company,
        benefits
    )
    is not null
