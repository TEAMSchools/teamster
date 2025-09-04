with

    applications as (select *, from {{ ref("stg_smartrecruiters__applications") }}),

    {# some records have rejected or other dates prior to "new" dates #}
    {# because reinstating candidates in a job does not create a new application id #}
    applications_status_after_new as (
        select applications.application_id, min(date_value) as date_next_status_new,
        from applications
        cross join
            unnest(
                [
                    case
                        when
                            applications.date_phone_screen_requested
                            > applications.date_new
                        then applications.date_phone_screen_requested
                    end,
                    case
                        when
                            applications.date_phone_screen_complete
                            > applications.date_new
                        then applications.date_phone_screen_complete
                    end,
                    case
                        when applications.date_demo > applications.date_new
                        then applications.date_demo
                    end,
                    case
                        when applications.date_offer > applications.date_new
                        then applications.date_offer
                    end,
                    case
                        when applications.date_hired > applications.date_new
                        then applications.date_hired
                    end,
                    case
                        when applications.date_rejected > applications.date_new
                        then applications.date_rejected
                    end
                ]
            ) as date_value
        where date_value is not null
        group by applications.application_id
    ),

    applications_status_after_lead as (
        select applications.application_id, min(date_value) as date_next_status_lead,
        from applications
        cross join
            unnest(
                [
                    case
                        when applications.date_new > applications.date_lead
                        then applications.date_new
                    end,
                    case
                        when
                            applications.date_phone_screen_requested
                            > applications.date_lead
                        then applications.date_phone_screen_requested
                    end,
                    case
                        when
                            applications.date_phone_screen_complete
                            > applications.date_lead
                        then applications.date_phone_screen_complete
                    end,
                    case
                        when applications.date_demo > applications.date_lead
                        then applications.date_demo
                    end,
                    case
                        when applications.date_offer > applications.date_lead
                        then applications.date_offer
                    end,
                    case
                        when applications.date_hired > applications.date_lead
                        then applications.date_hired
                    end,
                    case
                        when applications.date_rejected > applications.date_lead
                        then applications.date_rejected
                    end
                ]
            ) as date_value
        where date_value is not null
        group by applications.application_id
    ),

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
            applications.recruiters,
            applications.source,
            applications.source_subtype,
            applications.source_type,
            applications.subject_preference,
            recruiter_single,
            applications_status_after_new.date_next_status_new,
            applications_status_after_lead.date_next_status_lead,
            trim(subject_preference_single) as subject_preference_single,
            coalesce(
                applications.application_field_school_shared_with_miami,
                applications.application_field_school_shared_with_new_jersey
            ) as school_shared_with,
            coalesce(
                applications.application_field_resume_score, applications.average_rating
            ) as resume_score,

        from applications
        left join
            applications_status_after_new
            on applications.application_id
            = applications_status_after_new.application_id
        left join
            applications_status_after_lead
            on applications.application_id
            = applications_status_after_lead.application_id
        {# separating out multi-select fields for reporting #}
        cross join
            unnest(
                split(applications.subject_preference, ',')
            ) as subject_preference_single
        cross join unnest(split(applications.recruiters, ',')) as recruiter_single

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
            recruiter_single,
            source,
            source_subtype,
            source_type,
            subject_preference,
            subject_preference_single,
            school_shared_with,
            resume_score,
            date_next_status_new,
            date_next_status_lead,
            date_trunc(date_new, week(monday)) as application_week_start,  -- noqa: LT01
            date_diff(date_hired, date_new, day) as days_to_hire,
            {# average days to review uses current date in lieu of an application #}
            {# having a next stage noted #}
            if(
                date_next_status_new != '9999-12-31',
                date_diff(date_next_status_new, date_new, day),
                date_diff(current_date(), date_new, day)
            ) as days_new_to_other,
            if(
                date_next_status_lead != '9999-12-31',
                date_diff(date_next_status_lead, date_lead, day),
                date_diff(current_date(), date_lead, day)
            ) as days_lead_to_other,
            {# application considered reviewed when days between new or lead and next #}
            {# stage <= 7 days and a resume score has been added #}
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
        from applications_unnested

    )

select *,
from final
