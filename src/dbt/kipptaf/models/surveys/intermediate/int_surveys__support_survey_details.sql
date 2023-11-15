with
    response_identifiers as (
        select
            fr.form_id as survey_id,
            fr.info_title as survey_title,
            fr.response_id as survey_response_id,

            rt.academic_year as campaign_academic_year,
            rt.name as campaign_name,
            rt.code as campaign_reporting_term,

            timestamp(fr.create_time) as date_started,
            timestamp(fr.last_submitted_time) as date_submitted,

            safe_cast(
                regexp_extract(fr.text_value, r'\((\d{6})\)') as integer
            ) as respondent_df_employee_number,
            fr.respondent_email

        from {{ ref("base_google_forms__form_responses") }} as fr
        left join
            {{ ref("stg_reporting__terms") }} as rt
            on date(fr.last_submitted_time) between rt.start_date and rt.end_date
            and rt.type = 'SURVEY'
            and rt.code in ('SUP1', 'SUP2')
        where
            fr.question_item__question__question_id = '55f7fb30'
            and fr.form_id = '1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI'

        union distinct

        select
            fr.form_id as survey_id,
            fr.info_title as survey_title,
            fr.response_id as survey_response_id,

            rt.academic_year as campaign_academic_year,
            rt.name as campaign_name,
            rt.code as campaign_reporting_term,

            timestamp(fr.create_time) as date_started,
            timestamp(fr.last_submitted_time) as date_submitted,

            up.employee_number as respondent_df_employee_number,
            fr.respondent_email

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
            fr.question_item__question__question_id = '55f7fb30'
            and fr.form_id = '1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI'
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
    case
        when safe_cast(fr.text_value as integer) is null then 1 else 0
    end as is_open_ended,

    fi.abbreviation as question_shortname,
    fi.title as question_title,

    fr.text_value as answer,
    safe_cast(fr.text_value as integer) as answer_value,

    ri.respondent_df_employee_number,
    eh.preferred_name_lastfirst,
    ri.respondent_email,
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
inner join
    {{ source("google_forms", "src_google_forms__form_items_extension") }} as fi
    on fr.form_id = fi.form_id
    and fr.question_item__question__question_id = fi.question_id
inner join
    {{ ref("base_people__staff_roster_history") }} as eh
    on ri.respondent_df_employee_number = eh.employee_number
    and ri.date_submitted
    between eh.work_assignment__fivetran_start and eh.work_assignment__fivetran_end

    -- ADD HISTORIC DATA WITH UNION
    
