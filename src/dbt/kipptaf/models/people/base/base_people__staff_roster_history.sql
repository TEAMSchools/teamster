with
    with_dayforce as (
        select
            wp.associate_oid,
            wp.worker_id,
            wp.worker_original_hire_date,
            wp.worker_rehire_date,
            wp.worker_termination_date,
            wp.status_value,

            wp.work_assignment_id,
            wp.work_assignment_end_date,
            wp.work_assignment_end_timestamp,
            wp.work_assignment__fivetran_active,
            wp.work_assignment_hire_date,
            wp.work_assignment_actual_start_date,
            wp.work_assignment_seniority_date,
            wp.work_assignment_termination_date,
            wp.position_id,
            wp.job_title,
            wp.primary_indicator,
            wp.management_position_indicator,
            wp.is_prestart,

            wp.preferred_name_given_name,
            wp.preferred_name_middle_name,
            wp.preferred_name_family_name,
            wp.preferred_name_lastfirst,

            wp.preferred_salutation_legal_name,
            wp.legal_name_given_name,
            wp.legal_name_middle_name,
            wp.legal_name_family_name,
            wp.legal_name_nick_name,
            wp.legal_name_formatted_name,
            wp.legal_name_generation_affix,
            wp.legal_name_qualification_affix,

            wp.birth_name_family_name,

            wp.assignment_status_effective_date,
            wp.assignment_status,
            wp.assignment_status_reason,
            wp.assignment_status_prev,

            wp.report_to_associate_oid,
            wp.report_to_worker_id,
            wp.report_to_position_id,
            wp.report_to_preferred_name_family_name,
            wp.report_to_preferred_name_given_name,
            wp.report_to_preferred_name_lastfirst,

            wp.business_unit_assigned_code,
            wp.business_unit_assigned_name,
            wp.business_unit_home_code,
            wp.business_unit_home_name,

            wp.home_work_location_name,

            wp.department_assigned_code,
            wp.department_assigned_name,
            wp.department_home_code,
            wp.department_home_name,

            wp.communication_business_email,
            wp.communication_business_landline,
            wp.communication_business_mobile,
            wp.communication_person_email,
            wp.communication_person_landline,
            wp.communication_person_mobile,

            wp.worker_type,
            wp.worker_group_name,
            wp.worker_group_value,

            wp.payroll_file_number,
            wp.payroll_processing_status_short_name,
            wp.payroll_schedule_group_id,
            wp.payroll_group_code,

            wp.cost_number_assigned_code,
            wp.cost_number_assigned_name,
            wp.cost_number_home_code,
            wp.cost_number_home_name,

            wp.pay_cycle_short_name,

            wp.full_time_equivalence_ratio,

            wp.wage_law_coverage_name_long_name,
            wp.wage_law_coverage_short_name,

            wp.base_remuneration_effective_date,
            wp.base_remuneration_annual_rate_amount_amount_value,

            wp.additional_remuneration_effective_date,
            wp.additional_remuneration_rate_amount_value,
            wp.additional_remuneration_name,

            wp.standard_hour_hours_quantity,
            wp.standard_hour_unit_short_name,
            wp.standard_pay_period_hour_hours_quantity,

            wp.legal_address_city_name,
            wp.legal_address_country_code,
            wp.legal_address_country_subdivision_level_1,
            wp.legal_address_country_subdivision_level_2,
            wp.legal_address_line_one,
            wp.legal_address_line_two,
            wp.legal_address_line_three,
            wp.legal_address_postal_code,

            wp.birth_date,
            wp.ethnicity_long_name,
            wp.gender_long_name,
            wp.highest_education_level_long_name,

            wp.marital_status_effective_date,
            wp.marital_status_short_name,

            wp.military_discharge_date,
            wp.military_status_long_name,

            wp.tobacco_user_indicator,
            wp.disabled_indicator,
            wp.disability,

            wp.race_ethnicity_reporting,
            wp.race_long_name,

            wp.custom_covid_19_booster_1_date,
            wp.custom_covid_19_booster_1_type,
            wp.custom_covid_19_date_of_last_vaccine,
            wp.custom_covid_19_vaccine_type,
            wp.custom_employee_number,
            wp.custom_miami_aces_number,
            wp.custom_nj_pension_number,
            wp.custom_payroll_custom_area_1,
            wp.custom_payroll_custom_area_2,
            wp.custom_payroll_custom_area_3,
            wp.custom_payroll_data_control,
            wp.custom_wfmgr_accrual_profile,
            wp.custom_wfmgr_badge_number,
            wp.custom_wfmgr_ee_type,
            wp.custom_wfmgr_home_hyperfind,
            wp.custom_wfmgr_loa_return_date,
            wp.custom_wfmgr_loa,
            wp.custom_wfmgr_pay_rule,
            wp.custom_wfmgr_trigger,

            en.employee_number,

            rten.employee_number as report_to_employee_number,

            if(
                wp.work_assignment_start_date < '2021-01-01',
                '2021-01-01',
                wp.work_assignment_start_date
            ) as work_assignment_start_date,

            if(
                wp.work_assignment_start_timestamp
                < timestamp('2021-01-01', '{{ var("local_timezone") }}'),
                timestamp('2021-01-01', '{{ var("local_timezone") }}'),
                wp.work_assignment_start_timestamp
            ) as work_assignment_start_timestamp,
        from {{ ref("int_adp_workforce_now__worker_person") }} as wp
        inner join
            {{ ref("stg_people__employee_numbers") }} as en
            on wp.worker_id = en.adp_associate_id
            and en.is_active
        left join
            {{ ref("stg_people__employee_numbers") }} as rten
            on wp.report_to_worker_id = rten.adp_associate_id
            and rten.is_active
        /* after transistion from Dayforce */
        where wp.work_assignment_end_date >= '2021-01-01'

        union all

        select
            null as associate_oid,
            null as worker_id,

            original_hire_date as worker_original_hire_date,
            rehire_date as worker_rehire_date,
            termination_date as worker_termination_date,

            null as status_value,

            surrogate_key as work_assignment_id,
            effective_end_date as work_assignment_end_date,
            effective_end_timestamp as work_assignment_end_timestamp,
            is_active as work_assignment__fivetran_active,

            null as work_assignment_hire_date,

            work_assignment_effective_start_date as work_assignment_actual_start_date,

            null as work_assignment_seniority_date,
            null as work_assignment_termination_date,

            null as position_id,

            job_name as job_title,

            true as primary_indicator,
            null as management_position_indicator,
            false as is_prestart,

            preferred_first_name as preferred_name_given_name,

            null as preferred_name_middle_name,

            preferred_last_name as preferred_name_family_name,
            preferred_name_lastfirst,

            null as preferred_salutation_legal_name,

            legal_first_name as legal_name_given_name,

            null as legal_name_middle_name,

            legal_last_name as legal_name_family_name,

            null as legal_name_nick_name,
            null as legal_name_formatted_name,
            null as legal_name_generation_affix,
            null as legal_name_qualification_affix,
            null as birth_name_family_name,

            status_effective_start_date as assignment_status_effective_date,
            `status` as assignment_status,
            status_reason_description as assignment_status_reason,
            null as assignment_status_prev,

            null as report_to_associate_oid,
            null as report_to_worker_id,
            null as report_to_position_id,
            null as report_to_preferred_name_family_name,
            null as report_to_preferred_name_given_name,
            null as report_to_preferred_name_lastfirst,
            null as business_unit_assigned_code,

            legal_entity_name as business_unit_assigned_name,

            null as business_unit_home_code,

            legal_entity_name as business_unit_home_name,
            physical_location_name as home_work_location_name,

            null as department_assigned_code,

            department_name as department_assigned_name,

            null as department_home_code,

            department_name as department_home_name,

            null as communication_business_email,
            null as communication_business_landline,
            null as communication_business_mobile,
            null as communication_person_email,
            null as communication_person_landline,

            mobile_number as communication_person_mobile,
            pay_class_name as worker_type,

            null as worker_group_name,
            null as worker_group_value,
            null as payroll_file_number,
            null as payroll_processing_status_short_name,
            null as payroll_schedule_group_id,
            null as payroll_group_code,
            null as cost_number_assigned_code,
            null as cost_number_assigned_name,
            null as cost_number_home_code,
            null as cost_number_home_name,
            null as pay_cycle_short_name,
            null as full_time_equivalence_ratio,
            'Fair Labor Standards Act' as wage_law_coverage_name_long_name,

            flsa_status_name as wage_law_coverage_short_name,

            null as base_remuneration_effective_date,

            base_salary as base_remuneration_annual_rate_amount_amount_value,

            null as additional_remuneration_effective_date,
            null as additional_remuneration_rate_amount_value,
            null as additional_remuneration_name,
            null as standard_hour_hours_quantity,
            null as standard_hour_unit_short_name,
            null as standard_pay_period_hour_hours_quantity,

            city as legal_address_city_name,

            null as legal_address_country_code,

            `state` as legal_address_country_subdivision_level_1,

            null as legal_address_country_subdivision_level_2,

            `address` as legal_address_line_one,

            null as legal_address_line_two,
            null as legal_address_line_three,

            postal_code as legal_address_postal_code,
            birth_date,
            ethnicity as ethnicity_long_name,
            gender as gender_long_name,

            null as highest_education_level_long_name,
            null as marital_status_effective_date,
            null as marital_status_short_name,
            null as military_discharge_date,
            null as military_status_long_name,
            null as tobacco_user_indicator,
            null as disabled_indicator,
            null as disability,

            race_ethnicity_reporting,

            null as race_long_name,
            null as custom_covid_19_booster_1_date,
            null as custom_covid_19_booster_1_type,
            null as custom_covid_19_date_of_last_vaccine,
            null as custom_covid_19_vaccine_type,
            null as custom_employee_number,
            null as custom_miami_aces_number,
            null as custom_nj_pension_number,
            null as custom_payroll_custom_area_1,
            null as custom_payroll_custom_area_2,
            null as custom_payroll_custom_area_3,
            null as custom_payroll_data_control,
            null as custom_wfmgr_accrual_profile,
            null as custom_wfmgr_badge_number,
            null as custom_wfmgr_ee_type,
            null as custom_wfmgr_home_hyperfind,
            null as custom_wfmgr_loa_return_date,
            null as custom_wfmgr_loa,
            null as custom_wfmgr_pay_rule,
            null as custom_wfmgr_trigger,

            employee_number,
            manager_employee_number as report_to_employee_number,
            effective_start_date as work_assignment_start_date,
            effective_start_timestamp as work_assignment_start_timestamp,
        from {{ ref("base_dayforce__employee_history") }}
    )

select
    wd.* except (race_ethnicity_reporting),

    lc.reporting_school_id as home_work_location_reporting_school_id,
    lc.powerschool_school_id as home_work_location_powerschool_school_id,
    lc.deanslist_school_id as home_work_location_deanslist_school_id,
    lc.clean_name as home_work_location_reporting_name,
    lc.abbreviation as home_work_location_abbreviation,
    lc.grade_band as home_work_location_grade_band,
    lc.region as home_work_location_region,
    lc.is_campus as home_work_location_is_campus,
    lc.is_pathways as home_work_location_is_pathways,
    lc.dagster_code_location as home_work_location_dagster_code_location,

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

    case
        when coalesce(sis.gender_identity, wd.gender_long_name) = 'Female'
        then 'Cis Woman'
        when coalesce(sis.gender_identity, wd.gender_long_name) = 'Male'
        then 'Cis Man'
        else coalesce(sis.gender_identity, wd.gender_long_name)
    end as gender_identity,

    case
        when regexp_contains(sis.race_ethnicity, 'Latinx/Hispanic/Chicana(o)')
        then true
        when wd.ethnicity_long_name = 'Hispanic or Latino'
        then true
        else false
    end as is_hispanic,

    coalesce(
        sis.race_ethnicity_reporting, wd.race_ethnicity_reporting
    ) as race_ethnicity_reporting,

    coalesce(
        idps.powerschool_teacher_number, safe_cast(wd.employee_number as string)
    ) as powerschool_teacher_number,
from with_dayforce as wd
left join
    {{ ref("stg_people__location_crosswalk") }} as lc
    on wd.home_work_location_name = lc.name
left join
    {{ ref("stg_ldap__user_person") }} as ldap
    on wd.employee_number = ldap.employee_number
left join
    {{ ref("stg_people__powerschool_crosswalk") }} as idps
    on wd.employee_number = idps.employee_number
    and idps.is_active
left join
    {{ ref("int_surveys__staff_information_survey_pivot") }} as sis
    on wd.employee_number = sis.employee_number
left join
    {{ ref("stg_ldap__user_person") }} as rtldap
    on wd.report_to_employee_number = rtldap.employee_number
