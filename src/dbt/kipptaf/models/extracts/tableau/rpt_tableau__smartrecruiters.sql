with
    applications as (select *, from {{ ref("stg_smartrecruiters__applications") }}),

    applications_transformed as (
        select
            application_field_phone_interview_score as phone_interview_score,
            application_id,
            application_reason_for_rejection as reason_for_rejection,
            application_state,
            application_url,
            candidate_email,
            candidate_first_name,
            candidate_id,
            candidate_last_name,
            candidate_linkedin_profile_url,
            date_demo,
            date_hired,
            date_last_update,
            date_lead,
            date_new,
            date_offer,
            date_phone_screen_complete,
            date_phone_screen_requested,
            date_rejected,
            department_internal,
            department_org_field_value,
            job_city,
            job_title,
            recruiters,
            source,
            source_subtype,
            source_type,
            subject_preference,
            coalesce(
                application_field_school_shared_with_miami,
                application_field_school_shared_with_new_jersey
            ) as school_shared_with,
            coalesce(application_field_resume_score, average_rating) as resume_score,
            least(
                coalesce(date_rejected, '9999-12-31'),
                coalesce(date_phone_screen_requested, '9999-12-31'),
                coalesce(date_phone_screen_complete, '9999-12-31'),
                coalesce(date_demo, '9999-12-31'),
                coalesce(date_offer, '9999-12-31'),
                coalesce(date_hired, '9999-12-31')
            ) as date_next_status_new,
            least(
                coalesce(date_new, '9999-12-31'),
                coalesce(date_rejected, '9999-12-31'),
                coalesce(date_phone_screen_requested, '9999-12-31'),
                coalesce(date_phone_screen_complete, '9999-12-31'),
                coalesce(date_demo, '9999-12-31'),
                coalesce(date_offer, '9999-12-31'),
                coalesce(date_hired, '9999-12-31')
            ) as date_next_status_lead,
        from applications
    ),

    final as (
        select
            application_id,
            application_state,
            application_url,
            candidate_email,
            candidate_first_name,
            candidate_id,
            candidate_last_name,
            candidate_linkedin_profile_url,
            date_demo,
            date_hired,
            date_last_update,
            date_lead,
            date_new,
            date_offer,
            date_phone_screen_complete,
            date_phone_screen_requested,
            date_rejected,
            department_internal,
            department_org_field_value,
            job_city,
            job_title,
            phone_interview_score,
            reason_for_rejection,
            recruiters,
            source,
            source_subtype,
            source_type,
            subject_preference,
            school_shared_with,
            resume_score,
            date_next_status_new,
            date_next_status_lead,
            date_trunc(date_new, week(monday)) as application_week_start,  -- noqa: LT01

            case
                when
                    date_diff(date_next_status_new, date_new, day) <= 7
                    and resume_score is not null
                then true
                when
                    date_diff(date_next_status_lead, date_lead, day) <= 7
                    and resume_score is not null
                then true
                else false
            end as within_week_initial_review,
        from applications_transformed
    )
{# 
    final as (
        select *,
        from
            applications unpivot (
                date_value for status_type in (
                    demo_date,
                    hired_date,
                    new_date,
                    offer_date,
                    phone_screen_complete_date,
                    phone_screen_requested_date,
                    rejected_date
                )
            )
    ) #}
select *,
from final
