with
    applications_unnested as (
        select
            a.application_id,
            a.application_state,
            a.application_url,
            a.candidate_email,
            a.candidate_first_name,
            a.candidate_id,
            a.candidate_last_name,
            a.candidate_linkedin_profile_url,
            a.department_internal,
            a.department_org_field_value,
            a.job_city,
            a.job_title,
            a.source,
            a.source_subtype,
            a.source_type,
            a.time_in_application_state_new,
            a.time_in_application_state_in_review,
            a.time_in_application_state_lead,
            a.school_shared_with,
            a.phone_interview_score,
            a.application_reason_for_rejection as reason_for_rejection,
            a.recruiters as recruiter_multiple,
            a.subject_preference as subject_preference_multiple,
            a.demo_date_local as date_demo,
            a.hired_date_local as date_hired,
            a.last_update_date_local as date_last_update,
            a.lead_date_local as date_lead,
            a.new_date_local as date_new,
            a.offer_date_local as date_offer,
            a.phone_screen_complete_date_local as date_phone_screen_complete,
            a.phone_screen_requested_date_local as date_phone_screen_requested,
            a.rejected_date_local as date_rejected,

            recruiter,

            trim(subject_preference_single) as subject_preference,

            coalesce(a.resume_score, a.average_rating) as resume_score,

            (
                select min(d),
                from
                    unnest(
                        [
                            a.phone_screen_requested_date_local,
                            a.phone_screen_complete_date_local,
                            a.demo_date_local,
                            a.offer_date_local,
                            a.hired_date_local,
                            a.rejected_date_local
                        ]
                    ) as d
            ) as date_reviewed,

            /* App Review Week runs Thursday to Wednesday and is named for its
               Monday: +4 days moves Thursday onto that Monday */
            date_trunc(
                -- trunk-ignore(sqlfluff/LT01)
                date_add(a.new_date_local, interval 4 day), week(monday)
            ) as application_week_start,
        from {{ ref("stg_smartrecruiters__applications") }} as a
        /* separating out multi-select fields for reporting */
        cross join unnest(split(a.subject_preference, ',')) as subject_preference_single
        cross join unnest(split(a.recruiters, ',')) as recruiter
    ),

    add_dimensions_and_metrics as (
        select
            *,

            date_add(application_week_start, interval 7 day) as review_due_date,

            if(resume_score >= 3, 1, 0) as high_quality_candidate,

            date_add(application_week_start, interval 7 day)
            <= current_date('{{ var("local_timezone") }}') as is_review_due,

            case
                when
                    department_org_field_value in ('Teacher', 'Teaching Fellow')
                    and resume_score is not null
                    and date_reviewed < date_add(application_week_start, interval 7 day)
                then 1
                when department_org_field_value in ('Teacher', 'Teaching Fellow')
                then 0
                when
                    department_org_field_value not in ('Teacher', 'Teaching Fellow')
                    and time_in_application_state_new <= 7
                    and application_state != 'NEW'
                then 1
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
                when
                    date_diff(date_rejected, date_new, day) <= 7
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when
                    date_diff(date_phone_screen_requested, date_new, day) <= 7
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when
                    date_diff(date_phone_screen_complete, date_new, day) <= 7
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when
                    date_diff(date_demo, date_new, day) <= 7
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when
                    date_diff(date_offer, date_new, day) <= 7
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                when
                    date_diff(date_hired, date_new, day) <= 7
                    and resume_score is not null
                    and application_state not in ('NEW', 'IN_REVIEW')
                then 1
                else 0
            end as within_week_initial_review,

            date_diff(date_hired, date_new, day) as days_to_hire,
            date_diff(current_date(), date_last_update, day) as days_since_update,
        from applications_unnested
    )

select
    *,

    case
        when
            days_since_update >= 7
            and application_state
            not in ('HIRED', 'REJECTED', 'TRANSFERRED', 'WITHDRAWN')
        then 1
        else 0
    end as stalled_application,

    case
        when
            days_since_update >= 7
            and high_quality_candidate = 1
            and application_state
            not in ('HIRED', 'REJECTED', 'TRANSFERRED', 'WITHDRAWN')
        then 1
        else 0
    end as stalled_application_high_quality,
from add_dimensions_and_metrics
