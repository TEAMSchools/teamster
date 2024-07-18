select
    a.application_id,
    a.candidate_id,
    a.job_title,
    a.job_city,
    a.recruiters,
    a.department_internal,
    a.application_status,
    a.phone_interview_score,
    a.resume_score,
    a.new_date,
    a.phone_screen_requested_date,
    a.demo_date,
    a.offer_date,
    a.hired_date,
    a.candidate_source,
    a.candidate_source_type,
    a.candidate_source_subtype,

    b.candidate_last_first,
    b.candidate_email,
from {{ ref("stg_smartrecruiters__applications") }} as a
left join
    {{ ref("stg_smartrecruiters__applicants") }} as b on a.candidate_id = b.candidate_id
