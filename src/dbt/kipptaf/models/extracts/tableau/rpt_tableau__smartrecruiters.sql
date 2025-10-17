with

    applications as (select *, from {{ ref("stg_smartrecruiters__applications") }}),

    applications_unnested as (
        select
            applications.application_field_phone_interview_score
            as phone_interview_score,
            applications.application_id,
            applications.application_reason_for_rejection as reason_for_rejection,
            applications.application_state,
            applications.application_url,
            applications.candidate_email,
            applications.candidate_first_name,
            applications.candidate_id,
            applications.candidate_last_name,
            applications.candidate_linkedin_profile_url,
            applications.date_demo,
            applications.date_hired,
            applications.date_last_update,
            applications.date_lead,
            applications.date_new,
            applications.date_offer,
            applications.date_phone_screen_complete,
            applications.date_phone_screen_requested,
            applications.date_rejected,
            applications.department_internal,
            applications.department_org_field_value,
            applications.job_city,
            applications.job_title,
            applications.recruiters as recruiter_multiple,
            applications.source,
            applications.source_subtype,
            applications.source_type,
            applications.subject_preference as subject_preference_multiple,
            applications.time_in_application_state_new,
            applications.time_in_application_state_in_review,
            applications.time_in_application_state_lead,
            recruiter,
            date_trunc(applications.date_new, week(monday)) as application_week_start,  -- noqa: LT01,LT05
            trim(subject_preference_single) as subject_preference,
            coalesce(
                applications.application_field_school_shared_with_miami,
                applications.application_field_school_shared_with_new_jersey
            ) as school_shared_with,
            safe_cast(
                coalesce(
                    applications.application_field_resume_score,
                    applications.average_rating
                ) as int
            ) as resume_score,
        from applications
        {# separating out multi-select fields for reporting #}
        cross join
            unnest(
                split(applications.subject_preference, ',')
            ) as subject_preference_single
        cross join unnest(split(applications.recruiters, ',')) as recruiter

    ),

    add_dimensions_and_metrics as (
        select
            *,
            {# custom dimensions #}
            if(resume_score >= 3, 1, 0) as high_quality_candidate,
            case
                when
                    time_in_application_state_new <= 7
                    and resume_score is not null
                    and application_state != 'IN_REVIEW'
                then 1
                when
                    time_in_application_state_lead <= 7
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when date_diff(date_rejected,date_new,day) <= 7 
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when date_diff(date_phone_screen_requested,date_new,day) <= 7 
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when date_diff(date_phone_screen_complete,date_new,day) <= 7 
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when date_diff(date_demo,date_new,day) <= 7 
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when date_diff(date_offer,date_new,day) <= 7 
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when date_diff(date_hired,date_new,day) <= 7 
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                else 0
            end as within_week_initial_review,
            {# calculated metrics #}
            date_diff(date_hired, date_new, day) as days_to_hire,
            date_diff(current_date(), date_last_update, day) as days_since_update,
        from applications_unnested
    ),

    final as (
        select
            *,
            {# derived metrics #}
            case
                when
                    days_since_update >= 7
                    and application_state
                    not in ('HIRED', 'REJECTED', 'TRANSFERRED', 'WITHDRAWN')
                then 1
                else 0
            end as stalled_application,
            case
                when days_since_update >= 7 and high_quality_candidate = 1 then 1 else 0
            end as stalled_application_high_quality,
        from add_dimensions_and_metrics
    )

select *,
from final
