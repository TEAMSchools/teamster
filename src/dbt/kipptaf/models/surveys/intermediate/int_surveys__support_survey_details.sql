with
    response_identifiers as (
        select
            fr.form_id as survey_id,
            fr.info_title as survey_title,
            fr.response_id as survey_response_id,
            fr.respondent_email,

            rt.academic_year as campaign_academic_year,
            rt.name as campaign_name,
            rt.code as campaign_reporting_term,

            up.employee_number as respondent_df_employee_number,

            timestamp(fr.create_time) as date_started,
            timestamp(fr.last_submitted_time) as date_submitted,

        from {{ ref("base_google_forms__form_responses") }} as fr
        left join
            {{ ref("stg_reporting__terms") }} as rt
            on date(fr.last_submitted_time) between rt.start_date and rt.end_date
            and rt.type = 'SURVEY'
            and rt.code in ('SUP1', 'SUP2')
        inner join
            {{ ref("stg_ldap__user_person") }} as up
            on fr.respondent_email = up.google_email
        where
            fr.question_id = '55f7fb30'
            and fr.form_id = '1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI'
            and fr.rn_form_item_respondent_submitted_desc = 1
    )

select
    ri.survey_id,
    ri.survey_title,
    ri.survey_response_id,
    ri.date_started,
    ri.date_submitted,
    ri.campaign_academic_year,
    ri.campaign_name,
    ri.campaign_reporting_term,
    ri.respondent_df_employee_number,
    ri.respondent_email,

    fr.item_abbreviation as question_shortname,
    fr.item_title as question_title,
    fr.text_value as answer,
    safe_cast(fr.text_value as numeric) as answer_value,
    if(safe_cast(fr.text_value as integer) is null, 1, 0) as is_open_ended,

    eh.preferred_name_lastfirst,
    eh.management_position_indicator as is_manager,
    eh.department_home_name as respondent_department_name,
    eh.business_unit_home_name as respondent_legal_entity_name,
    eh.report_to_preferred_name_lastfirst as respondent_manager_name,
    eh.job_title as respondent_primary_job,
    eh.home_work_location_name as respondent_primary_site,
    eh.race_ethnicity_reporting,
    eh.gender_identity as gender,
from response_identifiers as ri
inner join
    {{ ref("base_google_forms__form_responses") }} as fr
    on ri.survey_id = fr.form_id
    and ri.survey_response_id = fr.response_id
    and fr.item_abbreviation != 'respondent_name'
inner join
    {{ ref("base_people__staff_roster_history") }} as eh
    on ri.respondent_df_employee_number = eh.employee_number
    and ri.date_submitted
    between eh.work_assignment__start_date and eh.work_assignment__end_date
    and eh.assignment_status not in ('Terminated', 'Deceased')

union all

select
    'historic_alchemer_cmo_support_survey' as survey_id,
    'CMO & Support Survey History' as survey_title,
    null as survey_response_id,
    null as date_started,
    timestamp(sda.date_submitted) as date_submitted,
    sda.campaign_academic_year,
    null as campaign_name,
    sda.campaign_reporting_term,
    sda.respondent_df_employee_number,
    null as respondent_email,

    sda.question_shortname as question_shortname,
    coalesce(fi.title, sda.question_shortname) as question_title,

    sda.answer,
    safe_cast(sda.answer_value as numeric) as answer_value,
    if(sda.answer_value is null, 1, 0) as is_open_ended,

    eh.preferred_name_lastfirst,
    eh.management_position_indicator as is_manager,
    eh.department_home_name as respondent_department_name,
    eh.business_unit_home_name as respondent_legal_entity_name,
    eh.report_to_preferred_name_lastfirst as respondent_manager_name,
    eh.job_title as respondent_primary_job,
    eh.home_work_location_name as respondent_primary_site,
    eh.race_ethnicity_reporting,
    eh.gender_identity as gender,
from {{ ref("stg_surveys__cmo_engagement_regional_survey_detail_archive") }} as sda
inner join
    {{ source("google_forms", "src_google_forms__form_items_extension") }} as fi
    on sda.question_shortname = fi.abbreviation
    and fi.form_id = '1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI'
left join
    {{ ref("base_people__staff_roster_history") }} as eh
    on sda.respondent_df_employee_number = eh.employee_number
    and timestamp(sda.date_submitted)
    between eh.work_assignment__start_date and eh.work_assignment__end_date
    and eh.assignment_status not in ('Terminated', 'Deceased')
