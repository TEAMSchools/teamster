with
    applications as (
        select
            application_id,
            candidate_id,
            candidate_first_name,
            candidate_last_name,
            --candidate_last_first,
            candidate_email,
            candidate_source,
            candidate_source_type,
            candidate_source_subtype,
            department_internal,
            job_title,
            job_city,
            recruiters,
            application_field_phone_interview_score as phone_interview_score,
            application_field_resume_score as resume_score,
            application_reason_for_rejection as reason_for_rejection,
            application_reason_for_withdrawal as reason_for_withdrawal,
            application_status,

            cast(application_state_hired_date as timestamp) as hired_date_timestamp,
            cast(application_state_new_date as timestamp) as new_date_timestamp,
            cast(application_state_offer_date as timestamp) as offer_date_timestamp,
            cast(
                application_state_rejected_date as timestamp
            ) as rejected_date_timestamp,
            cast(
                application_status_interview_demo_date as timestamp
            ) as demo_date_timestamp,
            cast(
                application_status_interview_phone_screen_complete_date as timestamp
            ) as phone_screen_complete_date_timestamp,
            cast(
                application_status_interview_phone_screen_requested_date as timestamp
            ) as phone_screen_requested_date_timestamp,
        from {{ source("smartrecruiters", "src_smartrecruiters__applications") }}
    )

select
    a.*,

    cast(new_date_timestamp as date) as new_date,
    cast(phone_screen_complete_date_timestamp as date) as phone_screen_complete_date,
    cast(phone_screen_requested_date_timestamp as date) as phone_screen_requested_date,
    cast(demo_date_timestamp as date) as demo_date,
    cast(offer_date_timestamp as date) as offer_date,
    cast(hired_date_timestamp as date) as hired_date,
from applications as a
