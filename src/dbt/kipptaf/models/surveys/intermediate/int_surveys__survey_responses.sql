select
    fr.form_id as survey_id,
    fr.info_title as survey_title,
    fr.response_id as survey_response_id,
    fr.text_value as answer,
    fr.item_title as question_title,
    fr.item_abbreviation as question_shortname,
    fr.rn_form_item_respondent_submitted_desc as rn,
    concat(
        'https://docs.google.com/forms/d/',
        fr.form_id,
        '/edit#response=',
        fr.response_id
    ) as survey_response_link,

    rt.code as survey_code,
    rt.type as survey_type,
    rt.academic_year,

    eh.employee_number,
    eh.preferred_name_lastfirst as respondent_name,
    eh.management_position_indicator as is_manager,
    eh.department_home_name as respondent_department_name,
    eh.business_unit_home_name as respondent_legal_entity_name,
    eh.report_to_preferred_name_lastfirst as respondent_manager_name,
    eh.job_title as respondent_primary_job,
    eh.home_work_location_name as respondent_primary_site,
    eh.race_ethnicity_reporting,
    eh.gender_identity as gender,
    eh.mail,
    eh.report_to_preferred_name_lastfirst as manager_name,
    eh.report_to_mail as manager_email,
    eh.report_to_user_principal_name as manager_user_principal_name,
    eh.alumni_status,
    eh.community_grew_up,
    eh.community_professional_exp,
    eh.level_of_education,
    eh.primary_grade_level_taught,
    eh.assignment_status,

    timestamp(fr.create_time) as date_started,
    timestamp(fr.last_submitted_time) as date_submitted,
    safe_cast(fr.text_value as numeric) as answer_value,
    case
        when safe_cast(fr.text_value as integer) is null then 1 else 0
    end as is_open_ended,
from {{ ref("base_google_forms__form_responses") }} as fr
inner join
    {{ ref("base_people__staff_roster_history") }} as eh
    on fr.respondent_email = eh.google_email
    and timestamp(fr.last_submitted_time)
    between eh.work_assignment_start_date and eh.work_assignment_end_date
left join
    {{ ref("stg_reporting__terms") }} as rt
    on rt.name = fr.info_title
    and date(fr.last_submitted_time) between rt.start_date and rt.end_date
    and eh.assignment_status not in ('Terminated', 'Deceased')

union all

select
    safe_cast(sr.survey_id as string) as survey_id,
    sr.survey_title as survey_title,
    safe_cast(sr.response_id as string) as survey_response_id,
    sr.response_value as answer,
    sr.question_title_english as question_title,
    sr.question_short_name as question_shortname,
    1 as rn,
    concat(
        sr.survey_link_default, '?snc=', sr.response_session_id, '&sg_navigate=start'
    ) as survey_response_link,

    regexp_extract(sr.campaign_name, r'\s(.*)') as survey_code,
    'SURVEY' as survey_type,
    sr.campaign_fiscal_year - 1 as academic_year,

    eh.employee_number,
    eh.preferred_name_lastfirst as respondent_name,
    eh.management_position_indicator as is_manager,
    eh.department_home_name as respondent_department_name,
    eh.business_unit_home_name as respondent_legal_entity_name,
    eh.report_to_preferred_name_lastfirst as respondent_manager_name,
    eh.job_title as respondent_primary_job,
    eh.home_work_location_name as respondent_primary_site,
    eh.race_ethnicity_reporting,
    eh.gender_identity as gender,
    eh.mail,
    eh.report_to_preferred_name_lastfirst as manager_name,
    eh.report_to_mail as manager_email,
    eh.report_to_user_principal_name as manager_user_principal_name,
    eh.alumni_status,
    eh.community_grew_up,
    eh.community_professional_exp,
    eh.level_of_education,
    eh.primary_grade_level_taught,
    eh.assignment_status,

    sr.response_date_started as date_started,
    sr.response_date_submitted as date_submitted,
    safe_cast(sr.response_value as numeric) as answer_value,
    case
        when safe_cast(sr.response_value as integer) is null then 1 else 0
    end as is_open_ended,
from {{ ref("base_alchemer__survey_results") }} as sr
left join
    {{ ref("stg_reporting__terms") }} as rt
    on rt.name = sr.survey_title
    and sr.response_date_submitted_date between rt.start_date and rt.end_date
inner join
    {{ ref("int_surveys__response_identifiers") }} as ri
    on sr.survey_id = ri.survey_id
    and sr.response_id = ri.response_id
inner join
    {{ ref("base_people__staff_roster_history") }} as eh
    on ri.respondent_employee_number = eh.employee_number
    and sr.response_date_submitted
    between eh.work_assignment_start_date and eh.work_assignment_end_date
    and eh.assignment_status not in ('Terminated', 'Deceased')
