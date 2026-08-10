-- trunk-ignore(sqlfluff/ST06): entity case fixed 3rd by Tableau RLS contract order
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
    eh.race_ethnicity_reporting as race_ethnicity,
    eh.gender_identity as gender,
    eh.reports_to_formatted_name as manager_name,
    eh.reports_to_user_principal_name as manager_user_principal_name,
    eh.alumni_status,
    eh.community_grew_up,
    eh.community_professional_exp,
    eh.level_of_education,
    eh.assignment_status,

    lc.location_clean_name,
    lc.campus_name,

    case
        eh.home_business_unit_name
        when 'TEAM'
        then 'TEAM Academy Charter School'
        when 'KCNA'
        then 'KIPP Cooper Norcross Academy'
        when 'MIA'
        then 'KIPP Miami'
        when 'KNJ'
        then 'KIPP TEAM and Family Schools Inc.'
        else eh.home_business_unit_name
    end as home_business_unit_name,

    eh.home_department_name,
    eh.job_function,
    eh.job_title,

    eh.mail,
    eh.user_principal_name,
    eh.sam_account_name,

    eh.reports_to_mail,
    eh.reports_to_sam_account_name,

    tgl.grade_level as primary_grade_level_taught,

    lower(sr.question_shortname) as question_shortname,

    regexp_replace(sr.answer, r'<[^>]*>', '') as answer,
    regexp_replace(sr.question_title, r'<[^>]*>', '') as question_title,
from {{ ref("int_surveys__survey_responses") }} as sr
inner join
    {{ ref("int_people__staff_roster_history") }} as eh
    on sr.respondent_employee_number = eh.employee_number
    and sr.date_submitted
    between eh.effective_date_start_timestamp and eh.effective_date_end_timestamp
    and eh.primary_indicator
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on eh.home_work_location_name = lc.location_name
left join
    {{ ref("int_students__teacher_grade_levels") }} as tgl
    on eh.powerschool_teacher_number = tgl.teachernumber
    and eh.home_work_location_dagster_code_location = tgl._dbt_source_project
    and sr.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
