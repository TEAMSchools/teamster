select
    sl.employee_number,
    sl.assignment_status,
    sl.preferred_name_lastfirst,
    sl.business_unit,
    sl.location,
    sl.department,
    sl.job_title,
    sl.hire_date,
    sl.survey,
    sl.academic_year,
    sl.survey_round,
    sl.is_current,
    sl.mail,
    sr.survey_response_id,
    if(sr.survey_response_id is not null, 1, 0) as completion,
from {{ ref("rpt_tableau__survey_links") }} as sl
left join
    {{ ref("rpt_tableau__survey_responses") }} as sr
    on sl.employee_number = sr.employee_number
    and sl.academic_year = sr.academic_year
    and sl.survey_round = sr.survey_code
where sr.round_rn is null or <= 1
