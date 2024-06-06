select
    application_id,
    job_city,
    recruiters,
    department_internal,
    job_title,
    application_state,
    source,
    source_type,
    source_subtype,
    application_reason_for_rejection as reason_for_rejection,
    application_state_hired_date as hired_date,
    application_state_in_review_date as in_review_date,
    application_state_interview_date as interview_date,
    application_state_new_date as new_date,
    application_state_offer_date as offer_date,
    application_status_interview_demo_date as demo_date,
    application_status_interview_performance_task_date as performance_task_date,
    application_status_interview_phone_screen_complete_date
    as phone_screen_complete_date,
    application_status_interview_phone_screen_requested_date
    as phone_screen_requested_date,
from {{ source("smartrecruiters", "src_smartrecruiters__applications") }}
