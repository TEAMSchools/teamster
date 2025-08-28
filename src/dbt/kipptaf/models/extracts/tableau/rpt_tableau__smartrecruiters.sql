with

    date_spine as (
        select
            date_week_start, date_add(date_week_start, interval 6 day) as date_week_end,
        from
            unnest(
                generate_date_array(
                    /* first Monday of reporting period for recruiters*/
                    '2020-10-05',
                    current_date('{{ var("local_timezone") }}'),
                    interval 1 week
                )
            ) as date_week_start
    ),

    applications as (
        select
            a.application_field_phone_interview_score as phone_interview_score,
            a.application_id,
            a.application_reason_for_rejection as reason_for_rejection,
            a.application_state,
            a.application_url,
            a.average_rating,
            a.candidate_email,
            a.candidate_first_name,
            a.candidate_id,
            a.candidate_last_name,
            a.candidate_linkedin_profile_url,
            a.department_internal,
            a.department_org_field_value,
            a.job_city,
            a.job_title,
            a.recruiters,
            a.source_subtype,
            a.source_type,
            a.source,
            a.new_date,
            a.hired_date,
            a.offer_date,
            a.demo_date,
            a.phone_screen_complete_date,
            a.phone_screen_requested_date,
            a.last_update_date,
            a.rejected_date,
            a.time_in_application_state_in_review,
            a.time_in_application_state_interview,
            a.time_in_application_state_lead,
            a.time_in_application_state_new,
            a.time_in_application_state_offered,
            a.time_in_application_status_in_review_resume_review,
            a.time_in_application_status_interview_demo,
            a.time_in_application_status_interview_phone_screen_complete,
            a.time_in_application_status_interview_phone_screen_requested,
            trim(subject_preference_unnest) as subject_preference,
            coalesce(
                a.application_field_school_shared_with_miami,
                a.application_field_school_shared_with_new_jersey
            ) as school_shared_with,
            coalesce(
                a.application_field_resume_score, a.average_rating
            ) as resume_score,
            case when a.hired_date is not null then 1 else 0 end as has_hired_status,
            case when a.offer_date is not null then 1 else 0 end as has_offer_status,
            case when a.demo_date is not null then 1 else 0 end as has_demo_status,
            case
                when a.phone_screen_complete_date is not null then 1 else 0
            end as has_phone_screen_complete_status,
            case
                when a.phone_screen_requested_date is not null then 1 else 0
            end as has_phone_screen_requested_status,
            case when a.new_date is not null then 1 else 0 end as has_new_status,
        from {{ ref("stg_smartrecruiters__applications") }} as a
        cross join unnest(split(a.subject_preference, ',')) as subject_preference_unnest

    ),

    applications_unpivoted as (
        select *,
        from
            applications unpivot (
                date_val for status_type in (
                    demo_date,
                    hired_date,
                    new_date,
                    offer_date,
                    phone_screen_complete_date,
                    phone_screen_requested_date
                )
            )
    )

select applications_unpivoted.*, date_spine.date_week_start, date_spine.date_week_end,
from applications_unpivoted
inner join
    date_spine
    on applications_unpivoted.date_val
    between date_spine.date_week_start and date_spine.date_week_end
