select
    s.survey_id,
    s.survey_title,
    s.survey_response_id,
    s.survey_question_id,
    s.answer,
    s.question_title,
    s.question_shortname,
    s.respondent_email,
    s.respondent_employee_number,
    s.respondent_preferred_name,
    s.answer_value,
    s.date_started,
    s.date_submitted,
    s.survey_response_link,
    s.round_rn,
    max(case when s.question_title = 'School Name:' then s.answer else null end) over (
        partition by s.survey_response_id
    ) as school_name,
from {{ ref("int_surveys__survey_responses") }} as s
left join
    {{ ref("int_people__staff_roster") }} as r
    on s.respondent_employee_number = r.employee_number
where s.survey_id = '1lYa4PDXK9_SfTx72BfJKgbA8F7NUS0ifYRo0pTp6ynQ'
