select
    w.associate_oid,
    w.effective_date_start,
    w.effective_date_end,
    w.effective_date_timestamp,
    w.is_current_record,
    w.worker_id__id_value as worker_id,
    w.worker_dates__original_hire_date as worker_original_hire_date,
    w.worker_dates__rehire_date as worker_rehire_date,
    w.worker_dates__termination_date as worker_termination_date,
    w.person__formatted_name as formatted_name,
    w.person__family_name_1 as family_name_1,
    w.person__given_name as given_name,
    w.person__legal_name__family_name_1 as legal_name__family_name_1,
    w.person__legal_name__given_name as legal_name__given_name,
    w.person__birth_date as birth_date,
    w.person__race_code_name as race_code,
    w.person__ethnicity_code_name as ethnicity_code,
    w.person__gender_code_name as gender_code,
    w.is_prestart,
    w.position_id,
    w.job_title,
    w.primary_indicator,
    w.management_position_indicator,
    w.assignment_status__status_code__name as assignment_status,
    w.home_work_location__name_code__name as home_work_location_name,
    w.worker_type_code__name as worker_type_code,
    w.wage_law_coverage__wage_law_name_code__name as wage_law_name,
    w.wage_law_coverage__coverage_code__name as wage_law_coverage,
    w.base_remuneration__annual_rate_amount__amount_value
    as base_remuneration_annual_rate_amount,
    w.communication__work_email__email_uri as work_email,
    w.communication__personal_email__email_uri as personal_email,
    w.custom_field__employee_number,
    w.wf_mgr_accrual_profile,
    w.wf_mgr_badge_number,
    w.wf_mgr_ee_type,
    w.wf_mgr_pay_rule,
    w.wf_mgr_trigger,
    w.organizational_unit__assigned__business_unit__code_value
    as assigned_business_unit_code,
    w.organizational_unit__assigned__business_unit__name as assigned_business_unit_name,
    w.organizational_unit__assigned__department__name as assigned_department_name,
    w.organizational_unit__home__business_unit__code_value as home_business_unit_code,
    w.organizational_unit__home__business_unit__name as home_business_unit_name,
    w.organizational_unit__home__department__name as home_department_name,
    w.reports_to_worker_id__id_value as reports_to_worker_id,

    en.employee_number,

    rten.employee_number as reports_to_employee_number,

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

    ldap.distinguished_name,
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

    rtldap.google_email as reports_to_google_email,

    coalesce(
        w.worker_dates__rehire_date, w.worker_dates__original_hire_date
    ) as worker_hire_date_recent,

    lower(ldap.sam_account_name) as sam_account_name,
    lower(ldap.user_principal_name) as user_principal_name,
    lower(ldap.mail) as mail,

    lower(rtldap.sam_account_name) as reports_to_sam_account_name,
    lower(rtldap.user_principal_name) as reports_to_user_principal_name,
    lower(rtldap.mail) as reports_to_mail,

    coalesce(
        idps.powerschool_teacher_number, cast(en.employee_number as string)
    ) as powerschool_teacher_number,

    coalesce(
        sis.race_ethnicity_reporting, w.race_ethnicity_reporting
    ) as race_ethnicity_reporting,

    case
        when coalesce(sis.gender_identity, w.person__gender_code_name) = 'Female'
        then 'Cis Woman'
        when coalesce(sis.gender_identity, w.person__gender_code_name) = 'Male'
        then 'Cis Man'
        else coalesce(sis.gender_identity, w.person__gender_code_name)
    end as gender_identity,

    case
        when contains_substr(sis.race_ethnicity, 'Latinx/Hispanic/Chicana(o)')
        then true
        when w.person__ethnicity_code_name = 'Hispanic or Latino'
        then true
        else false
    end as is_hispanic,

    {{
        dbt_utils.generate_surrogate_key(
            field_list=[
                "w.assignment_status__status_code__name",
                "w.base_remuneration__annual_rate_amount__amount_value",
                "w.home_work_location__name_code__name",
                "w.job_title",
                "w.organizational_unit__assigned__business_unit__name",
                "w.organizational_unit__assigned__department__name",
                "w.reports_to_worker_id__id_value",
                "w.wage_law_coverage__coverage_code__name",
                "w.wf_mgr_accrual_profile",
                "w.wf_mgr_badge_number",
                "w.wf_mgr_ee_type",
                "w.wf_mgr_pay_rule",
            ]
        )
    }} as surrogate_key,
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
    on w.home_work_location__name_code__name = lc.name
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
