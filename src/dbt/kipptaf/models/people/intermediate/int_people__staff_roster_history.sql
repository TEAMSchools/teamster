select
    w.* except (race_ethnicity_reporting),

    en.employee_number,

    rten.employee_number as report_to_employee_number,

    lc.region as home_work_location_region,
    lc.dagster_code_location as home_work_location_dagster_code_location,
    lc.clean_name as home_work_location_reporting_name,
    lc.abbreviation as home_work_location_abbreviation,
    lc.grade_band as home_work_location_grade_band,
    lc.reporting_school_id as home_work_location_reporting_school_id,
    lc.powerschool_school_id as home_work_location_powerschool_school_id,
    lc.deanslist_school_id as home_work_location_deanslist_school_id,
    lc.is_campus as home_work_location_is_campus,
    lc.is_pathways as home_work_location_is_pathways,

    ldap.mail,
    ldap.distinguished_name,
    ldap.user_principal_name,
    ldap.sam_account_name,
    ldap.physical_delivery_office_name,
    ldap.uac_account_disable,
    ldap.google_email,

    sis.last_submitted_timestamp as survey_last_submitted_timestamp,
    sis.additional_languages,
    sis.alumni_status,
    sis.community_grew_up,
    sis.community_professional_exp,
    sis.languages_spoken,
    sis.level_of_education,
    sis.path_to_education,
    sis.race_ethnicity,
    sis.relay_status,
    sis.undergraduate_school,
    sis.years_exp_outside_kipp,
    sis.years_teaching_in_njfl,
    sis.years_teaching_outside_njfl,

    rtldap.user_principal_name as report_to_user_principal_name,
    rtldap.mail as report_to_mail,
    rtldap.sam_account_name as report_to_sam_account_name,
    rtldap.google_email as report_to_google_email,

    coalesce(
        idps.powerschool_teacher_number, cast(en.employee_number as string)
    ) as powerschool_teacher_number,

    coalesce(
        sis.race_ethnicity_reporting, w.race_ethnicity_reporting
    ) as race_ethnicity_reporting,

    case
        when coalesce(sis.gender_identity, w.person__gender_code__long_name) = 'Female'
        then 'Cis Woman'
        when coalesce(sis.gender_identity, w.person__gender_code__long_name) = 'Male'
        then 'Cis Man'
        else coalesce(sis.gender_identity, w.person__gender_code__long_name)
    end as gender_identity,

    case
        when contains_substr(sis.race_ethnicity, 'Latinx/Hispanic/Chicana(o)')
        then true
        when w.person__ethnicity_code__long_name = 'Hispanic or Latino'
        then true
        else false
    end as is_hispanic,
from {{ ref("int_adp_workforce_now__workers") }} as w
inner join
    {{ ref("stg_people__employee_numbers") }} as en
    on w.worker_id__id_value = en.adp_associate_id
    and en.is_active
left join
    {{ ref("stg_people__employee_numbers") }} as rten
    on w.reports_to_worker_id__id_value = rten.adp_associate_id
    and rten.is_active
left join
    {{ ref("stg_people__location_crosswalk") }} as lc
    on w.home_work_location_name = lc.name
left join
    {{ ref("stg_ldap__user_person") }} as ldap
    on en.employee_number = ldap.employee_number
left join
    {{ ref("stg_people__powerschool_crosswalk") }} as idps
    on en.employee_number = idps.employee_number
    and idps.is_active
left join
    {{ ref("int_surveys__staff_information_survey_pivot") }} as sis
    on en.employee_number = sis.employee_number
left join
    {{ ref("stg_ldap__user_person") }} as rtldap
    on rten.employee_number = rtldap.employee_number
