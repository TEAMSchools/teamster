with
    response_identifiers as (
        select
            fr.form_id as survey_id,
            fr.info_title as survey_title,
            fr.response_id as survey_response_id,
            fr.respondent_email,
            fr.create_timestamp as date_started,
            fr.last_submitted_timestamp as date_submitted,

            up.employee_number as respondent_df_employee_number,

            rt.academic_year as campaign_academic_year,
            rt.name as campaign_name,
            rt.code as campaign_reporting_term,

            safe_cast(
                regexp_extract(fr.text_value, r'\((\d{6})\)') as integer
            ) as subject_df_employee_number,
        from {{ ref("base_google_forms__form_responses") }} as fr
        inner join
            {{ ref("stg_ldap__user_person") }} as up
            on fr.respondent_email = up.google_email
        left join
            {{ ref("stg_reporting__terms") }} as rt
            on fr.last_submitted_date_local between rt.start_date and rt.end_date
            and rt.type = 'SURVEY'
            and rt.code in ('MGR1', 'MGR2')
        where
            fr.form_id = '1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'
            and fr.question_id = '315a6c37'
    ),

    deduped_ri as (
        select
            survey_id,
            survey_title,
            survey_response_id,
            respondent_email,
            campaign_academic_year,
            campaign_name,
            campaign_reporting_term,
            respondent_df_employee_number,
            subject_df_employee_number,
            date_started,
            date_submitted,

            row_number() over (
                partition by
                    survey_id,
                    survey_response_id,
                    campaign_academic_year,
                    campaign_reporting_term,
                    respondent_df_employee_number,
                    subject_df_employee_number
            ) as rn_cur,
        from response_identifiers
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
    ri.subject_df_employee_number,
    ri.respondent_email,

    fr.item_abbreviation as question_shortname,
    fr.item_title as question_title,
    fr.text_value as answer,

    safe_cast(fr.text_value as numeric) as answer_value,

    if(safe_cast(fr.text_value as integer) is null, 1, 0) as is_open_ended,

    reh.preferred_name_lastfirst as respondent_preferred_name,
    reh.race_ethnicity_reporting as respondent_race_ethnicity_reporting,
    reh.gender_identity as respondent_gender,

    sr.preferred_name_lastfirst as subject_preferred_name,
    sr.management_position_indicator as is_manager,
    sr.department_home_name as subject_department_name,
    sr.business_unit_home_name as subject_legal_entity_name,
    sr.report_to_preferred_name_lastfirst as subject_manager_name,
    sr.job_title as subject_primary_job,
    sr.home_work_location_name as subject_primary_site,
    sr.race_ethnicity_reporting as subject_race_ethnicity_reporting,
    sr.gender_identity as subject_gender,

    lower(sr.sam_account_name) as subject_samaccountname,
    lower(sr.report_to_sam_account_name) as subject_manager_samaccountname,
    lower(sr.user_principal_name) as subject_userprincipalname,
    lower(sr.report_to_user_principal_name) as subject_manager_userprincipalname,
from deduped_ri as ri
inner join
    {{ ref("base_google_forms__form_responses") }} as fr
    on ri.survey_id = fr.form_id
    and ri.survey_response_id = fr.response_id
    and fr.item_abbreviation
    not in ('respondent_employee_number', 'subject_employee_number')
    and ri.rn_cur = 1
inner join
    {{ ref("base_people__staff_roster_history") }} as reh
    on ri.respondent_df_employee_number = reh.employee_number
    and ri.date_submitted
    between reh.work_assignment_start_timestamp and reh.work_assignment_end_timestamp
    and reh.assignment_status not in ('Terminated', 'Deceased')
inner join
    {{ ref("base_people__staff_roster") }} as sr
    on ri.subject_df_employee_number = sr.employee_number

union all

select
    'historic_alchemer_Manager_survey' as survey_id,
    'Manager Survey' as survey_title,
    null as survey_response_id,
    null as date_started,

    timestamp(sda.date_submitted) as date_submitted,

    sda.campaign_academic_year,

    null as campaign_name,

    sda.campaign_reporting_term,
    sda.respondent_df_employee_number,
    sda.subject_df_employee_number,

    null as respondent_email,

    sda.question_shortname,

    coalesce(fi.title, sda.question_shortname) as question_title,

    sda.answer,

    safe_cast(sda.answer_value as numeric) as answer_value,

    if(sda.answer_value is null, 1, 0) as is_open_ended,

    reh.preferred_name_lastfirst as respondent_preferred_name,
    reh.race_ethnicity_reporting as respondent_race_ethnicity_reporting,
    reh.gender_identity as respondent_gender,

    sr.preferred_name_lastfirst as subject_preferred_name,
    sr.management_position_indicator as is_manager,
    sr.department_home_name as subject_department_name,
    sr.business_unit_home_name as subject_legal_entity_name,
    sr.report_to_preferred_name_lastfirst as subject_manager_name,
    sr.job_title as subject_primary_job,
    sr.home_work_location_name as subject_primary_site,
    sr.race_ethnicity_reporting as subject_race_ethnicity_reporting,
    sr.gender_identity as subject_gender,

    lower(sr.sam_account_name) as subject_samaccountname,
    lower(sr.report_to_sam_account_name) as subject_manager_samaccountname,
    lower(sr.user_principal_name) as subject_userprincipalname,
    lower(sr.report_to_user_principal_name) as subject_manager_userprincipalname,
from {{ ref("stg_surveys__manager_survey_detail_archive") }} as sda
inner join
    {{ ref("stg_google_forms__form_items_extension") }} as fi
    on sda.question_shortname = fi.abbreviation
    and fi.form_id = '1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'
inner join
    {{ ref("base_people__staff_roster") }} as sr
    on sda.subject_df_employee_number = sr.employee_number
left join
    {{ ref("base_people__staff_roster_history") }} as reh
    on sda.respondent_df_employee_number = reh.employee_number
    and sda.date_submitted
    between reh.work_assignment_start_timestamp and reh.work_assignment_end_timestamp
    and reh.assignment_status not in ('Terminated', 'Deceased')
