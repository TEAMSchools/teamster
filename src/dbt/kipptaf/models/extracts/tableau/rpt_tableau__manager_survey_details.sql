-- trunk-ignore(sqlfluff/ST06): contract column order is mandated
select
    msd.effective_survey_response_id,
    msd.survey_id,
    msd.survey_title,
    msd.survey_response_id,
    msd.date_started,
    msd.date_submitted,
    msd.campaign_academic_year,
    msd.campaign_name,
    msd.campaign_reporting_term,
    msd.respondent_df_employee_number,
    msd.subject_df_employee_number,
    msd.respondent_email,
    msd.survey_question_id,
    msd.question_shortname,
    msd.question_title,
    msd.answer,
    msd.answer_value,
    msd.is_open_ended,
    msd.respondent_preferred_name,
    msd.respondent_race_ethnicity_reporting,
    msd.respondent_gender,
    msd.subject_preferred_name,
    msd.is_manager,
    msd.subject_manager_name,
    msd.subject_race_ethnicity_reporting,
    msd.subject_gender,
    msd.subject_manager_userprincipalname,

    lc.location_clean_name,
    lc.campus_name,

    case
        sr.home_business_unit_name
        when 'TEAM'
        then 'TEAM Academy Charter School'
        when 'KCNA'
        then 'KIPP Cooper Norcross Academy'
        when 'MIA'
        then 'KIPP Miami'
        when 'KNJ'
        then 'KIPP TEAM and Family Schools Inc.'
        else sr.home_business_unit_name
    end as home_business_unit_name,
    sr.home_department_name,
    sr.job_function,
    sr.job_title,

    sr.mail,
    sr.user_principal_name,
    sr.sam_account_name,

    sr.reports_to_mail,
    sr.reports_to_sam_account_name,
from {{ ref("int_surveys__manager_survey_details") }} as msd
left join
    {{ ref("int_people__staff_roster") }} as sr
    on msd.subject_df_employee_number = sr.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr.home_work_location_name = lc.location_name
