select
    application_id,
    candidate_id,
    job_city,
    recruiters,
    department_internal,
    job_title,
    application_status,
    candidate_first_name,
    candidate_last_name,
    --candidate_last_first,
    candidate_source,
    candidate_source_type,
    candidate_source_subtype,
    reason_for_rejection,

    status_type,
    date_val,
from
    {{ ref("stg_smartrecruiters__applications") }} unpivot (
        date_val for status_type in (
            demo_date,
            hired_date,
            new_date,
            offer_date,
            phone_screen_complete_date,
            phone_screen_requested_date
        )
    )
