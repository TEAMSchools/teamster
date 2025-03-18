select
    academic_year,
    unique_id,
    entity,
    city,
    grade_band,
    school,
    recruitment_group,
    adp_department,
    adp_job_title,
    display_name,
    culture,
    flex,
from {{ source("people", "src_people__staffing_model") }}
