with
    applications as (
        select
            application_id,
            candidate_id,
            job_city,
            recruiters,
            department_internal,
            job_title,
            application_status,
            reason_for_rejection,
            phone_interview_score,
            resume_score,
            status_type,
            date_val,
        from
            {{ ref("stg_smartrecruiters__applications") }} unpivot (
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

select
    s.*,
    a.application_id,
    a.job_city,
    a.recruiters,
    a.department_internal,
    a.job_title,
    a.application_status,
    a.reason_for_rejection,
    a.phone_interview_score,
    a.resume_score,
    a.status_type,
    a.date_val,
from applications as a
left join
    {{ ref("stg_smartrecruiters__applicants") }} as s on a.candidate_id = s.candidate_id
