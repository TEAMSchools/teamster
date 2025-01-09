select
    sl.employee_number,
    sl.assignment_status,
    sl.preferred_name_lastfirst,
    sl.business_unit,
    sl.location,
    sl.department,
    sl.job_title,
    sl.hire_date,
    sl.mail,
    sl.google_email,
    sl.report_to_employee_number,
    sl.report_to_preferred_name_lastfirst,
    sl.samaccountname,
    sl.username,
    sl.survey,
    sl.link,
    sl.assignment,

    if(sr.date_submitted is not null, 1, 0) as completion,

    max(datetime(date_submitted, 'America/New_York')) as date_submitted,

from {{ ref("rpt_tableau__survey_links") }} as sl
left join
    {{ ref("rpt_tableau__survey_responses") }} as sr
    on sl.employee_number = sr.employee_number
    and sl.academic_year = sr.academic_year
    and sl.survey_round = sr.survey_code
group by
    sl.employee_number,
    sl.assignment_status,
    sl.preferred_name_lastfirst,
    sl.business_unit,
    sl.location,
    sl.department,
    sl.job_title,
    sl.hire_date,
    sl.mail,
    sl.google_email,
    sl.report_to_employee_number,
    sl.report_to_preferred_name_lastfirst,
    sl.samaccountname,
    sl.username,
    sl.survey,
    sl.link,
    sl.assignment,
    sr.date_submitted
