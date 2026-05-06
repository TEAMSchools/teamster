select
    {{ dbt_utils.generate_surrogate_key(["app.application_id"]) }}
    as job_candidate_application_key,

    {{ dbt_utils.generate_surrogate_key(["app.candidate_id"]) }} as job_candidate_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["app.job_title", "app.department_internal", "app.job_city"]
        )
    }} as job_posting_key,

    loc.location_key as shared_with_location_key,

    app.new_date as created_date_key,

    app.application_state as state,
    app.application_reason_for_rejection as reason_for_rejection,
    app.application_reason_for_withdrawal as reason_for_withdrawal,
    app.application_status_before_rejection as status_before_rejection,
    app.application_status_before_withdrawal as status_before_withdrawal,
    app.source,
    app.source_type,
    app.source_subtype,
    app.subject_preference,
    app.average_rating,
    app.resume_score,

    app.new_datetime as created_timestamp,
    app.lead_date,
    app.lead_datetime as lead_timestamp,
    app.hired_date,
    app.hired_datetime as hired_timestamp,
    app.offer_date,
    app.offer_datetime as offer_timestamp,
    app.rejected_date,
    app.rejected_datetime as rejected_timestamp,
    app.last_update_date as last_updated_date,
    app.last_update_datetime as last_update_timestamp,
    app.demo_date,
    app.demo_datetime as demo_timestamp,
    app.phone_screen_requested_date,
    app.phone_screen_requested_datetime as phone_screen_requested_timestamp,
    app.phone_screen_complete_date,
    app.phone_screen_complete_datetime as phone_screen_complete_timestamp,
    app.invited_to_selection_day_date,
    app.invited_to_selection_day_datetime as invited_to_selection_day_timestamp,
    app.selection_day_date,
    app.selection_day_datetime as selection_day_timestamp,

    app.time_in_application_state_new,
    app.time_in_application_state_lead,
    app.time_in_application_state_in_review,
    app.time_in_application_state_interview,
    app.time_in_application_state_offered,
    app.time_in_application_status_in_review_resume_review,
    app.time_in_application_status_interview_demo,
    app.time_in_application_status_interview_phone_screen_requested,
    app.time_in_application_status_interview_phone_screen_complete,

    app.application_field_phone_interview_score as phone_interview_score,
    app.application_url as url,

    safe_cast(
        app.application_status_interview_performance_task_date as timestamp
    ) as status_interview_performance_task_timestamp,
from {{ ref("stg_smartrecruiters__applications") }} as app
left join
    {{ ref("int_people__location_crosswalk") }} as loc
    on app.school_shared_with = loc.location_name
    and not loc.location_is_pathways
    and loc.location_clean_name <> 'KIPP Whittier Elementary'
