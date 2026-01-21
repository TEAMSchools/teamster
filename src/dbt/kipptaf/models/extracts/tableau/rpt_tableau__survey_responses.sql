select
    sr.survey_id,
    sr.survey_title,
    sr.survey_response_id,
    sr.survey_response_link,
    sr.term_code as survey_code,

    'SURVEY' as survey_type,

    sr.academic_year,
    sr.date_started,
    sr.date_submitted,
    sr.answer_value,
    sr.is_open_ended,
    sr.round_rn,

    eh.employee_number,
    eh.formatted_name as respondent_name,
    eh.management_position_indicator as is_manager,
    eh.home_department_name as department,
    eh.home_business_unit_name as legal_entity,
    eh.reports_to_formatted_name as manager,
    eh.job_title,
    eh.home_work_location_name as `location`,
    eh.race_ethnicity_reporting as race_ethnicity,
    eh.gender_identity as gender,
    eh.mail,
    eh.reports_to_formatted_name as manager_name,
    eh.reports_to_mail as manager_email,
    eh.reports_to_user_principal_name as manager_user_principal_name,
    eh.alumni_status,
    eh.community_grew_up,
    eh.community_professional_exp,
    eh.level_of_education,
    eh.assignment_status,

    tgl.grade_level as primary_grade_level_taught,

    lower(sr.question_shortname) as question_shortname,

    regexp_replace(sr.answer, r'<[^>]*>', '') as answer,
    regexp_replace(sr.question_title, r'<[^>]*>', '') as question_title,
from {{ ref("int_surveys__survey_responses") }} as sr
left join
    {{ ref("int_people__staff_roster_history") }} as eh
    on sr.respondent_email = eh.google_email
    and sr.date_submitted
    between eh.effective_date_start_timestamp and eh.effective_date_end_timestamp
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on eh.powerschool_teacher_number = tgl.teachernumber
    and sr.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
where eh.primary_indicator
