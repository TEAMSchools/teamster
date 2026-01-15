with
    applications as (
        select
            * except (
                application_field_school_shared_with_miami,
                application_field_school_shared_with_new_jersey,
                application_last_update_date,
                application_state_hired_date,
                application_state_lead_date,
                application_state_new_date,
                application_state_offer_date,
                application_state_rejected_date,
                application_status_interview_demo_date,
                application_status_interview_invited_to_selection_day_date,
                application_status_interview_phone_screen_complete_date,
                application_status_interview_phone_screen_requested_date,
                application_status_interview_selection_day_date,
                average_rating,
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

            cast(application_state_hired_date as datetime) as hired_datetime,
            cast(application_state_new_date as datetime) as new_datetime,
            cast(application_state_lead_date as datetime) as lead_datetime,
            cast(application_state_offer_date as datetime) as offer_datetime,
            cast(application_state_rejected_date as datetime) as rejected_datetime,
            cast(application_status_interview_demo_date as datetime) as demo_datetime,
            cast(
                application_status_interview_phone_screen_complete_date as datetime
            ) as phone_screen_complete_datetime,
            cast(
                application_status_interview_phone_screen_requested_date as datetime
            ) as phone_screen_requested_datetime,
            cast(application_last_update_date as datetime) as last_update_datetime,
            cast(
                application_status_interview_invited_to_selection_day_date as datetime
            ) as invited_to_selection_day_datetime,
            cast(
                application_status_interview_selection_day_date as datetime
            ) as selection_day_datetime,

            cast(
                time_in_application_state_in_review as int
            ) as time_in_application_state_in_review,
            cast(
                time_in_application_state_interview as int
            ) as time_in_application_state_interview,
            cast(
                time_in_application_state_lead as int
            ) as time_in_application_state_lead,
            cast(time_in_application_state_new as int) as time_in_application_state_new,
            cast(
                time_in_application_state_offered as int
            ) as time_in_application_state_offered,
            cast(
                time_in_application_status_in_review_resume_review as int
            ) as time_in_application_status_in_review_resume_review,
            cast(
                time_in_application_status_interview_demo as int
            ) as time_in_application_status_interview_demo,
            cast(
                time_in_application_status_interview_phone_screen_complete as int
            ) as time_in_application_status_interview_phone_screen_complete,
            cast(
                time_in_application_status_interview_phone_screen_requested as int
            ) as time_in_application_status_interview_phone_screen_requested,
            cast(application_field_resume_score as int) as resume_score,

            cast(average_rating as numeric) as average_rating,

            coalesce(
                application_field_school_shared_with_miami,
                application_field_school_shared_with_new_jersey
            ) as school_shared_with,

            coalesce(
                screening_question_answer_knjm_application_subject_preference,
                'No Preference'
            ) as subject_preference,
        from {{ source("smartrecruiters", "src_smartrecruiters__applications") }}
    )

select
    *,

    cast(demo_datetime as date) as demo_date,
    cast(hired_datetime as date) as hired_date,
    cast(invited_to_selection_day_datetime as date) as invited_to_selection_day_date,
    cast(last_update_datetime as date) as last_update_date,
    cast(lead_datetime as date) as lead_date,
    cast(new_datetime as date) as new_date,
    cast(offer_datetime as date) as offer_date,
    cast(phone_screen_complete_datetime as date) as phone_screen_complete_date,
    cast(phone_screen_requested_datetime as date) as phone_screen_requested_date,
    cast(rejected_datetime as date) as rejected_date,
    cast(selection_day_datetime as date) as selection_day_date,
from applications
