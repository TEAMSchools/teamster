with
    applications as (
        select
            * except (
                application_state_hired_date,
                application_state_new_date,
                application_state_offer_date,
                application_state_rejected_date,
                application_last_update_date,
                application_status_interview_demo_date,
                application_status_interview_phone_screen_complete_date,
                application_status_interview_phone_screen_requested_date,
                screening_question_answer_knjm_application_subject_preference
            ),
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
            datetime(application_last_update_date) as last_update_datetime,

            if(
                screening_question_answer_knjm_application_subject_preference is null,
                'No Preference',
                screening_question_answer_knjm_application_subject_preference
            ) as subject_preference,
        from {{ source("smartrecruiters", "src_smartrecruiters__applications") }}
    )

select
    *,

    date(new_datetime) as new_date,
    date(phone_screen_complete_datetime) as phone_screen_complete_date,
    date(phone_screen_requested_datetime) as phone_screen_requested_date,
    date(demo_datetime) as demo_date,
    date(offer_datetime) as offer_date,
    date(hired_datetime) as hired_date,
    date(rejected_datetime) as rejected_date,
    date(last_update_datetime) as last_update_date,
from applications
