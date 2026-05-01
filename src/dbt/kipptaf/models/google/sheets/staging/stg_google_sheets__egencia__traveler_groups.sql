select
    adp_home_business_unit_name,
    adp_department_home_name,
    adp_job_title,
    egencia_traveler_group,

    adp_home_work_location_name as location_clean_name,
from {{ source("google_sheets", "src_google_sheets__egencia__traveler_groups") }}
