select
    wp.work_assignment_id,
    wp.work_assignment_worker_id as worker_id,
    wp.work_assignment_actual_start_date,
    wp.work_assignment_hire_date,
    wp.work_assignment_termination_date,
    if
    (
        work_assignment_assignment_status_effective_date
        > current_date('America/New_York')
        and work_assignment_assignment_status_long_name = 'Active'
        and (
            work_assignment_assignment_status_long_name_prev is null
            or work_assignment_assignment_status_long_name_prev = 'Terminated'
        ),
        'Pre-Start',
        work_assignment_assignment_status_long_name
    ) as assignment_status,
    coalesce(
        wp.work_assignment_assignment_status_reason_long_name,
        wp.work_assignment_assignment_status_reason_short_name
    ) as assignment_status_reason,
    wp.work_assignment_assignment_status_effective_date
    as assignment_status_effective_date,
    wp.work_assignment_management_position_indicator as management_position_indicator,
    wp.work_assignment_payroll_processing_status_short_name
    as payroll_processing_status_short_name,
    wp.work_assignment_payroll_group_code as payroll_group_code,
    wp.work_assignment_payroll_file_number as payroll_file_number,
    wp.work_assignment_payroll_schedule_group_id as payroll_schedule_group_id,
    wp.work_assignment_position_id as position_id,
    wp.work_assignment_primary_indicator as primary_indicator,
    wp.work_assignment_pay_cycle_short_name as pay_cycle_short_name,
    coalesce(
        wp.work_assignment_home_work_location_name_long_name,
        wp.work_assignment_home_work_location_name_short_name
    ) as home_work_location_name,
    wp.work_assignment_job_title as job_title,
    wp.work_assignment_wage_law_coverage_name_long_name
    as wage_law_coverage_name_long_name,
    wp.work_assignment_wage_law_coverage_short_name as wage_law_coverage_short_name,
    wp.work_assignment_seniority_date,
    coalesce(
        wp.work_assignment_worker_type_long_name,
        wp.work_assignment_worker_type_short_name
    ) as worker_type,
    wp.work_assignment_standard_pay_period_hour_hours_quantity
    as standard_pay_period_hour_hours_quantity,
    wp.work_assignment_standard_hour_hours_quantity as standard_hour_hours_quantity,
    wp.work_assignment_standard_hour_unit_short_name as standard_hour_unit_short_name,
    wp.work_assignment_full_time_equivalence_ratio as full_time_equivalence_ratio,
    wp.work_assignment_custom_payroll_custom_area_1 as custom_payroll_custom_area_1,
    wp.work_assignment_custom_payroll_custom_area_2 as custom_payroll_custom_area_2,
    wp.work_assignment_custom_payroll_custom_area_3 as custom_payroll_custom_area_3,
    wp.work_assignment_custom_payroll_data_control as custom_payroll_data_control,

    wp.worker_associate_oid as associate_oid,
    wp.worker_status_value as status_value,
    wp.worker_original_hire_date,
    wp.worker_rehire_date,
    wp.worker_termination_date,
    wp.worker_custom_miami_aces_number as custom_miami_aces_number,
    wp.worker_custom_nj_pension_number as custom_nj_pension_number,
    wp.worker_custom_employee_number as custom_employee_number,
    wp.worker_custom_wfmgr_accrual_profile as custom_wfmgr_accrual_profile,
    wp.worker_custom_wfmgr_badge_number as custom_wfmgr_badge_number,
    wp.worker_custom_wfmgr_ee_type as custom_wfmgr_ee_type,
    wp.worker_custom_wfmgr_home_hyperfind as custom_wfmgr_home_hyperfind,
    wp.worker_custom_wfmgr_loa_return_date as custom_wfmgr_loa_return_date,
    wp.worker_custom_wfmgr_loa as custom_wfmgr_loa,
    wp.worker_custom_wfmgr_pay_rule as custom_wfmgr_pay_rule,
    wp.worker_custom_wfmgr_trigger as custom_wfmgr_trigger,

    wp.preferred_salutation_legal_name,
    wp.person_legal_name_given_name as legal_name_given_name,
    wp.person_legal_name_middle_name as legal_name_middle_name,
    wp.person_legal_name_family_name_1 as legal_name_family_name,
    wp.person_legal_name_formatted_name as legal_name_formatted_name,
    wp.person_legal_name_nick_name as legal_name_nick_name,
    wp.person_legal_name_generation_affix as legal_name_generation_affix,
    wp.person_legal_name_qualification_affix as legal_name_qualification_affix,
    coalesce(
        wp.person_preferred_name_given_name, wp.person_legal_name_given_name
    ) as preferred_name_given_name,
    coalesce(
        wp.person_preferred_name_middle_name, wp.person_legal_name_middle_name
    ) as preferred_name_middle_name,
    coalesce(
        wp.person_preferred_name_family_name_1, wp.person_legal_name_family_name_1
    ) as preferred_name_family_name,
    wp.person_birth_name_family_name_1 as birth_name_family_name,
    wp.person_legal_address_line_one as legal_address_line_one,
    wp.person_legal_address_line_two as legal_address_line_two,
    wp.person_legal_address_line_three as legal_address_line_three,
    wp.person_legal_address_city_name as legal_address_city_name,
    wp.person_legal_address_country_code as legal_address_country_code,
    wp.person_legal_address_country_subdivision_level_1
    as legal_address_country_subdivision_level_1,
    wp.person_legal_address_country_subdivision_level_2
    as legal_address_country_subdivision_level_2,
    wp.person_legal_address_postal_code as legal_address_postal_code,
    wp.person_birth_date as birth_date,
    wp.person_gender_long_name as gender_long_name,
    wp.person_ethnicity_long_name as ethnicity_long_name,
    wp.person_race_long_name as race_long_name,
    wp.person_marital_status_short_name as marital_status_short_name,
    wp.person_marital_status_effective_date as marital_status_effective_date,
    wp.person_military_status_long_name as military_status_long_name,
    wp.person_military_discharge_date as military_discharge_date,
    wp.person_highest_education_level_long_name as highest_education_level_long_name,
    wp.person_tobacco_user_indicator as tobacco_user_indicator,
    wp.person_disabled_indicator as disabled_indicator,
    wp.person_custom_attended_relay as custom_attended_relay,
    wp.person_custom_covid_19_booster_1_date as custom_covid_19_booster_1_date,
    wp.person_custom_covid_19_booster_1_type as custom_covid_19_booster_1_type,
    wp.person_custom_covid_19_date_of_last_vaccine
    as custom_covid_19_date_of_last_vaccine,
    wp.person_custom_covid_19_vaccine_type as custom_covid_19_vaccine_type,
    wp.person_custom_kipp_alumni_status as custom_kipp_alumni_status,
    wp.person_custom_preferred_gender as custom_preferred_gender,
    wp.person_custom_years_of_professional_experience_before_joining
    as custom_years_of_professional_experience_before_joining,
    wp.person_custom_years_teaching_in_any_state as custom_years_teaching_in_any_state,
    wp.person_custom_years_teaching_in_nj_or_fl as custom_years_teaching_in_nj_or_fl,

    wp.disability_long_name as disability,

    coalesce(
        wp.organizational_unit_business_unit_assigned_name_long_name,
        wp.organizational_unit_business_unit_assigned_name_short_name
    ) as business_unit_assigned_name,
    wp.organizational_unit_business_unit_assigned_name as business_unit_assigned_code,
    coalesce(
        wp.organizational_unit_business_unit_home_name_long_name,
        wp.organizational_unit_business_unit_home_name_short_name
    ) as business_unit_home_name,
    wp.organizational_unit_business_unit_home_name as business_unit_home_code,
    wp.organizational_unit_cost_number_assigned_name_short_name
    as cost_number_assigned_name,
    wp.organizational_unit_cost_number_assigned_name as cost_number_assigned_code,
    wp.organizational_unit_cost_number_home_name_short_name as cost_number_home_name,
    wp.organizational_unit_cost_number_home_name as cost_number_home_code,
    coalesce(
        wp.organizational_unit_department_assigned_name_long_name,
        wp.organizational_unit_department_assigned_name_short_name
    ) as department_assigned_name,
    wp.organizational_unit_department_assigned_name as department_assigned_code,
    coalesce(
        wp.organizational_unit_department_home_name_long_name,
        wp.organizational_unit_department_home_name_short_name
    ) as department_home_name,
    wp.organizational_unit_department_home_name as department_home_code,

    wp.base_remuneration_effective_date,
    wp.base_remuneration_annual_rate_amount_amount_value,

    wp.additional_remuneration_effective_date,
    wp.additional_remuneration_rate_amount_value,
    wp.additional_remuneration_name_short_name as additional_remuneration_name,

    wp.communication_person_email,
    wp.communication_person_mobile,
    wp.communication_business_email,

    wp.group_name_long_name as worker_group_name,
    coalesce(wp.group_group_long_name, wp.group_group_short_name) as worker_group_value,

    wp.report_to_id as report_to_associate_oid,
    wp.report_to_position_id,
    wp.report_to_report_to_worker_id as report_to_worker_id,

    wp.communication_person_landline,
    wp.communication_business_mobile,
    wp.communication_business_landline,

    en.employee_number,

    enm.employee_number as report_to_employee_number,

    ldap.mail,
    ldap.distinguished_name,
    ldap.user_principal_name,
    ldap.sam_account_name,
    ldap.physical_delivery_office_name,
    ldap.uac_account_disable,

{#- work_assignment__fivetran_active,
    work_assignment__fivetran_start,
    work_assignment__fivetran_end,
    work_assignment_assignment_status_short_name,
    work_assignment_assignment_status_value,
    work_assignment_pay_cycle,
    work_assignment_home_work_location_name,
    work_assignment_home_work_location_address_line_one,
    work_assignment_home_work_location_address_line_two,
    work_assignment_home_work_location_address_city_name,
    work_assignment_home_work_location_address_postal_code,
    work_assignment_home_work_location_address_country_subdivision_level_1,
    work_assignment_home_work_location_address_country_code,
    work_assignment_job,
    work_assignment_job_short_name,
    work_assignment_job_long_name,
    work_assignment_wage_law_coverage_name,
    work_assignment_wage_law_coverage_value,
    work_assignment_worker_type,
    work_assignment_standard_hour_unit,
    work_assignment_assignment_status_reason,
    worker__fivetran_deleted,
    worker_custom_employee_number,
    person_legal_name_generation_affix_short_name,
    person_legal_name_qualification_affix_long_name,
    person_legal_address_name,
    person_legal_address_name_long_name,
    person_legal_address_name_short_name,
    person_gender,
    person_gender_short_name,
    person_ethnicity,
    person_ethnicity_short_name,
    person_race,
    person_race_short_name,
    person_marital_status,
    person_military_status,
    person_military_status_short_name,
    person_highest_education_level,
    person_highest_education_level_short_name,
    disability_value,
    base_remuneration_annual_rate_amount_name_short_name,
    base_remuneration_annual_rate_amount_currency_code,
    base_remuneration_pay_period_rate_amount_name_short_name,
    base_remuneration_pay_period_rate_amount_amount_value,
    base_remuneration_pay_period_rate_amount_currency_code,
    base_remuneration_hourly_rate_amount_name_short_name,
    base_remuneration_hourly_rate_amount_amount_value,
    base_remuneration_hourly_rate_amount_currency_code,
    base_remuneration_daily_rate_amount_name_short_name,
    base_remuneration_daily_rate_amount_amount_value,
    base_remuneration_daily_rate_amount_currency_code,
    base_remuneration_annual_rate_amount_name,
    base_remuneration_pay_period_rate_amount_name,
    base_remuneration_hourly_rate_amount_name,
    base_remuneration_daily_rate_amount_name,
    additional_remuneration_id,
    additional_remuneration_name,
    additional_remuneration_rate_currency_code,
    group_id,
    group_name,
    personal_address_id,
    personal_address_type,
    personal_address_name,
    personal_address_name_short_name,
    other_personal_address_type_short_name,
    other_personal_address_name_long_name,
    other_personal_address_line_one,
    other_personal_address_line_two,
    other_personal_address_city_name,
    other_personal_address_postal_code,
    other_personal_address_country_subdivision_level_1,
    other_personal_address_country_subdivision_level_2,
    other_personal_address_country_code,
    location_id,
    location_address_name,
    location_address_name_long_name,
    location_address_line_one,
    location_address_line_two,
    location_address_city_name,
    location_address_country_subdivision_level_1,
    location_address_country_subdivision_level_2,
    location_address_country_code,
    location_address_postal_code,
    location_address_name_short_name, #}
from {{ ref("base_adp_workforce_now__worker_person") }} as wp
inner join
    {{ ref("stg_people__employee_numbers") }} as en
    on wp.work_assignment_worker_id = en.adp_associate_id
    and en.is_active
left join
    {{ ref("stg_people__employee_numbers") }} as enm
    on wp.report_to_report_to_worker_id = enm.adp_associate_id
    and enm.is_active
left join
    {{ ref("stg_ldap__user_person") }} as ldap
    on en.employee_number = ldap.employee_number
where wp.work_assignment__fivetran_active and wp.work_assignment_primary_indicator
