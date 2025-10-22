with
    applications as (
        select
            * except (
                application_state_hired_date,
                application_state_new_date,
                application_state_offer_date,
                application_state_rejected_date,
                application_state_lead_date,
                application_last_update_date,
                application_status_interview_demo_date,
                application_status_interview_phone_screen_complete_date,
                application_status_interview_phone_screen_requested_date,
                screening_question_answer_knjm_application_subject_preference,
                time_in_application_state_in_review,
                time_in_application_state_interview,
                time_in_application_state_lead,
                time_in_application_state_new,
                time_in_application_state_offered,
                time_in_application_status_in_review_resume_review,
                time_in_application_status_interview_demo,
                time_in_application_status_interview_phone_screen_complete,
                time_in_application_status_interview_phone_screen_requested
            ),

            datetime(application_state_hired_date) as hired_datetime,
            datetime(application_state_new_date) as new_datetime,
            datetime(application_state_lead_date) as lead_datetime,
            datetime(application_state_offer_date) as offer_datetime,
            datetime(application_state_rejected_date) as rejected_datetime,
            datetime(application_status_interview_demo_date) as demo_datetime,
            datetime(
                application_status_interview_phone_screen_complete_date
            ) as phone_screen_complete_datetime,
            datetime(
                application_status_interview_phone_screen_requested_date
            ) as phone_screen_requested_datetime,
            datetime(application_last_update_date) as last_update_datetime,
            safe_cast(
                time_in_application_state_in_review as int
            ) as time_in_application_state_in_review,
            safe_cast(
                time_in_application_state_interview as int
            ) as time_in_application_state_interview,
            safe_cast(
                time_in_application_state_lead as int
            ) as time_in_application_state_lead,
            safe_cast(
                time_in_application_state_new as int
            ) as time_in_application_state_new,
            safe_cast(
                time_in_application_state_offered as int
            ) as time_in_application_state_offered,
            safe_cast(
                time_in_application_status_in_review_resume_review as int
            ) as time_in_application_status_in_review_resume_review,
            safe_cast(
                time_in_application_status_interview_demo as int
            ) as time_in_application_status_interview_demo,
            safe_cast(
                time_in_application_status_interview_phone_screen_complete as int
            ) as time_in_application_status_interview_phone_screen_complete,
            safe_cast(
                time_in_application_status_interview_phone_screen_requested as int
            ) as time_in_application_status_interview_phone_screen_requested,
            if(
                screening_question_answer_knjm_application_subject_preference is null,
                'No Preference',
                screening_question_answer_knjm_application_subject_preference
            ) as subject_preference,
        from {{ source("smartrecruiters", "src_smartrecruiters__applications") }}
    )

select
    *,

    date(new_datetime) as date_new,
    date(phone_screen_complete_datetime) as date_phone_screen_complete,
    date(phone_screen_requested_datetime) as date_phone_screen_requested,
    date(demo_datetime) as date_demo,
    date(offer_datetime) as date_offer,
    date(hired_datetime) as date_hired,
    date(rejected_datetime) as date_rejected,
    date(last_update_datetime) as date_last_update,
    date(lead_datetime) as date_lead,
from applications
