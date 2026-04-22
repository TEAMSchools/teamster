select
    {{ dbt_utils.generate_surrogate_key(["application_id"]) }}
    as job_candidate_application_key,

    {{ dbt_utils.generate_surrogate_key(["candidate_id"]) }} as job_candidate_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["job_title", "department_internal", "job_city"]
        )
    }} as job_posting_key,

    if(
        school_shared_with is not null,
        {{ dbt_utils.generate_surrogate_key(["school_shared_with"]) }},
        cast(null as string)
    ) as shared_with_location_key,

    new_date as created_date_key,

    application_state as state,
    application_reason_for_rejection as reason_for_rejection,
    application_reason_for_withdrawal as reason_for_withdrawal,
    application_status_before_rejection as status_before_rejection,
    application_status_before_withdrawal as status_before_withdrawal,
    source,
    source_type,
    source_subtype,
    subject_preference,
    average_rating,
    resume_score,

    new_datetime as created_timestamp,
    lead_date,
    lead_datetime as lead_timestamp,
    hired_date,
    hired_datetime as hired_timestamp,
    offer_date,
    offer_datetime as offer_timestamp,
    rejected_date,
    rejected_datetime as rejected_timestamp,
    last_update_date as last_updated_date,
    last_update_datetime as last_update_timestamp,
    demo_date,
    demo_datetime as demo_timestamp,
    phone_screen_requested_date,
    phone_screen_requested_datetime as phone_screen_requested_timestamp,
    phone_screen_complete_date,
    phone_screen_complete_datetime as phone_screen_complete_timestamp,
    invited_to_selection_day_date,
    invited_to_selection_day_datetime as invited_to_selection_day_timestamp,
    selection_day_date,
    selection_day_datetime as selection_day_timestamp,

    time_in_application_state_new,
    time_in_application_state_lead,
    time_in_application_state_in_review,
    time_in_application_state_interview,
    time_in_application_state_offered,
    time_in_application_status_in_review_resume_review,
    time_in_application_status_interview_demo,
    time_in_application_status_interview_phone_screen_requested,
    time_in_application_status_interview_phone_screen_complete,

    application_field_phone_interview_score as phone_interview_score,
    application_url as url,

    safe_cast(
        application_status_interview_performance_task_date as timestamp
    ) as status_interview_performance_task_timestamp,
from {{ ref("stg_smartrecruiters__applications") }}
