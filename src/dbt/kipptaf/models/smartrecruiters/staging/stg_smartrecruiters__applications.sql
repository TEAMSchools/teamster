with
    applications as (
        select
            application_id,
            candidate_id,
            department_internal,
            job_title,
            job_city,
            recruiters,
            application_status,
            application_field_phone_interview_score as phone_interview_score,
            application_field_resume_score as resume_score,
            application_reason_for_rejection as reason_for_rejection,
            application_reason_for_withdrawal as reason_for_withdrawal,

            datetime(application_state_hired_date) as hired_datetime,
            datetime(application_state_new_date) as new_datetime,
            datetime(application_state_offer_date) as offer_datetime,
            datetime(application_state_rejected_date) as rejected_datetime,
            datetime(application_status_interview_demo_date) as demo_datetime,
            datetime(
                application_status_interview_phone_screen_complete_date
            ) as phone_screen_complete_datetime,
            datetime(
                application_status_interview_phone_screen_requested_date
            ) as phone_screen_requested_datetime,
        from {{ source("smartrecruiters", "src_smartrecruiters__applications") }}
    )

select
    a.*,

    date(new_datetime) as new_date,
    date(phone_screen_complete_datetime) as phone_screen_complete_date,
    date(phone_screen_requested_datetime) as phone_screen_requested_date,
    date(demo_datetime) as demo_date,
    date(offer_datetime) as offer_date,
    date(hired_datetime) as hired_date,
from applications as a
