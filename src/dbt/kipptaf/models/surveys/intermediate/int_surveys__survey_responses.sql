select
    fr.form_id as survey_id,
    fr.info_title as survey_title,
    fr.response_id as survey_response_id,
    fr.respondent_email,
    fr.text_value as answer,

    rt.name,
    rt.code,
    rt.type,

    fi.abbreviation as question_shortname,
    fi.title as question_title,

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

    timestamp(fr.create_time) as date_started,
    timestamp(fr.last_submitted_time) as date_submitted,
    safe_cast(fr.text_value as numeric) as answer_value,
    case
        when safe_cast(fr.text_value as integer) is null then 1 else 0
    end as is_open_ended,
from {{ ref("base_google_forms__form_responses") }} as fr
left join
    {{ ref("stg_reporting__terms") }} as rt
    on rt.name = fr.info_title
    and date(fr.last_submitted_time) between rt.start_date and rt.end_date
inner join
    {{ ref("stg_ldap__user_person") }} as up on fr.respondent_email = up.google_email
inner join
    {{ source("google_forms", "src_google_forms__form_items_extension") }} as fi
    on fr.form_id = fi.form_id
    and fr.question_item__question__question_id = fi.question_id
inner join
    {{ ref("base_people__staff_roster_history") }} as eh
    on up.employee_number = eh.employee_number
    and eh.assignment_status not in ('Terminated', 'Deceased')
    and timestamp(fr.last_submitted_time)
    between eh.work_assignment__fivetran_start and eh.work_assignment__fivetran_end
where fi.abbreviation != 'respondent_name'
