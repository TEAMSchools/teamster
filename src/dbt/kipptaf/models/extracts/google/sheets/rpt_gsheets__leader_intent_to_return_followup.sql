select
    lp.employee_number,
    lp.preferred_name_lastfirst,
    lp.job_title,
    lp.department,
    lp.business_unit,
    lp.location,
    lp.mail,
    lp.report_to_preferred_name_lastfirst,
    lp.report_to_mail,
from {{ ref("int_surveys__leader_intent_to_return_population") }} as lp
left join
    {{ ref("int_surveys__survey_submissions") }} as ss
    on lp.employee_number = ss.respondent_employee_number
    and lp.academic_year = ss.academic_year
    and lp.survey_round = ss.term_code
    and ss.round_rn = 1
where lp.is_current and ss.respondent_employee_number is null
