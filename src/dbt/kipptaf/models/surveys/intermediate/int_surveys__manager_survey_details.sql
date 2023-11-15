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

            safe_cast(
                regexp_extract(fr.text_value, r'\((\d{6})\)') as integer
            ) as subject_df_employee_number,

            timestamp(fr.create_time) as date_started,
            timestamp(fr.last_submitted_time) as date_submitted,

        from {{ ref("base_google_forms__form_responses") }} as fr
        left join
            {{ ref("stg_reporting__terms") }} as rt
            on date(fr.last_submitted_time) between rt.start_date and rt.end_date
            and rt.type = 'SURVEY'
            and rt.code in ('MGR1', 'MGR2')
        inner join
            {{ ref("stg_ldap__user_person") }} as up
            on fr.respondent_email = up.google_email
        where
            fr.question_item__question__question_id = '315a6c37'
            and fr.form_id = '1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'
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
    ri.subject_df_employee_number,
    ri.respondent_email,

    fi.abbreviation as question_shortname,
    fi.title as question_title,

    fr.text_value as answer,
    safe_cast(fr.text_value as numeric) as answer_value,
    case
        when safe_cast(fr.text_value as integer) is null then 1 else 0
    end as is_open_ended,

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

from response_identifiers as ri
inner join
    {{ ref("base_google_forms__form_responses") }} as fr
    on ri.survey_id = fr.form_id
    and ri.survey_response_id = fr.response_id
inner join
    {{ source("google_forms", "src_google_forms__form_items_extension") }} as fi
    on fr.form_id = fi.form_id
    and fr.question_item__question__question_id = fi.question_id
inner join
    {{ ref("base_people__staff_roster_history") }} as reh
    on ri.respondent_df_employee_number = reh.employee_number
    and ri.date_submitted
    between reh.work_assignment__fivetran_start and reh.work_assignment__fivetran_end
inner join
    {{ ref("base_people__staff_roster") }} as sr
    on ri.subject_df_employee_number = sr.employee_number
where
    fi.abbreviation != 'respondent_employee_number'
    and fi.abbreviation != 'subject_employee_number'

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
    sda.question_shortname as question_shortname,
    coalesce(fi.title, sda.question_shortname) as question_title,
    sda.answer,
    safe_cast(sda.answer_value as numeric) as answer_value,
    case when sda.answer_value is null then 1 else 0 end as is_open_ended,
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
    {{ source("google_forms", "src_google_forms__form_items_extension") }} as fi
    on fi.form_id = '1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0'
    and sda.question_shortname = fi.abbreviation
left join
    {{ ref("base_people__staff_roster_history") }} as reh
    on sda.respondent_df_employee_number = reh.employee_number
    and sda.date_submitted
    between reh.work_assignment__fivetran_start and reh.work_assignment__fivetran_end
inner join
    {{ ref("base_people__staff_roster") }} as sr
    on sda.subject_df_employee_number = sr.employee_number
