select
    w.work_assignment_id,
    w.work_assignment_worker_id as worker_id,
    w.work_assignment_position_id as position_id,
    w.work_assignment_primary_indicator as primary_indicator,
    w.work_assignment_start_date,
    w.work_assignment_end_date,
    w.work_assignment_start_timestamp,
    w.work_assignment_end_timestamp,
    w.work_assignment_hire_date,
    w.work_assignment_actual_start_date,
    w.work_assignment_termination_date,
    w.work_assignment__fivetran_active,
    w.work_assignment_assignment_status_long_name as assignment_status,
    w.work_assignment_assignment_status_long_name_lag as assignment_status_lag,
    w.work_assignment_assignment_status_reason as assignment_status_reason,
    w.work_assignment_assignment_status_effective_date
    as assignment_status_effective_date,
    w.work_assignment_management_position_indicator as management_position_indicator,
    w.work_assignment_payroll_processing_status_short_name
    as payroll_processing_status_short_name,
    w.work_assignment_payroll_group_code as payroll_group_code,
    w.work_assignment_payroll_file_number as payroll_file_number,
    w.work_assignment_payroll_schedule_group_id as payroll_schedule_group_id,
    w.work_assignment_pay_cycle_short_name as pay_cycle_short_name,
    w.work_assignment_job_title as job_title,
    w.work_assignment_wage_law_coverage_name_long_name
    as wage_law_coverage_name_long_name,
    w.work_assignment_wage_law_coverage_short_name as wage_law_coverage_short_name,
    w.work_assignment_seniority_date,
    w.work_assignment_standard_pay_period_hour_hours_quantity
    as standard_pay_period_hour_hours_quantity,
    w.work_assignment_standard_hour_hours_quantity as standard_hour_hours_quantity,
    w.work_assignment_standard_hour_unit_short_name as standard_hour_unit_short_name,
    w.work_assignment_full_time_equivalence_ratio as full_time_equivalence_ratio,
    w.work_assignment_custom_payroll_custom_area_1 as custom_payroll_custom_area_1,
    w.work_assignment_custom_payroll_custom_area_2 as custom_payroll_custom_area_2,
    w.work_assignment_custom_payroll_custom_area_3 as custom_payroll_custom_area_3,
    w.work_assignment_custom_payroll_data_control as custom_payroll_data_control,
    w.work_assignment__base_remuneration__effective_date
    as base_remuneration_effective_date,
    w.work_assignment__base_remuneration__annual_rate_amount__amount_value
    as base_remuneration_annual_rate_amount_amount_value,
    w.work_assignment_home_work_location_name as home_work_location_name,
    w.work_assignment_is_prestart as is_prestart,
    w.work_assignment_worker_type as worker_type,

    w.reports_to_associate_oid as report_to_associate_oid,
    w.reports_to_position_id as report_to_position_id,
    w.reports_to_worker_id__id_value as report_to_worker_id,

    w.worker_associate_oid as associate_oid,
    w.worker_status_value as status_value,
    w.worker_original_hire_date,
    w.worker_rehire_date,
    w.worker_termination_date,
    w.worker_custom_employee_number as custom_employee_number,
    w.worker_custom_miami_aces_number as custom_miami_aces_number,
    w.worker_custom_nj_pension_number as custom_nj_pension_number,
    w.worker_custom_wfmgr_accrual_profile as custom_wfmgr_accrual_profile,
    w.worker_custom_wfmgr_badge_number as custom_wfmgr_badge_number,
    w.worker_custom_wfmgr_ee_type as custom_wfmgr_ee_type,
    w.worker_custom_wfmgr_home_hyperfind as custom_wfmgr_home_hyperfind,
    w.worker_custom_wfmgr_loa as custom_wfmgr_loa,
    w.worker_custom_wfmgr_loa_return_date as custom_wfmgr_loa_return_date,
    w.worker_custom_wfmgr_pay_rule as custom_wfmgr_pay_rule,
    w.worker_custom_wfmgr_trigger as custom_wfmgr_trigger,

    w.worker_group_name,
    w.worker_group_value,

    w.organizational_unit_business_unit_assigned_code as business_unit_assigned_code,
    w.organizational_unit_business_unit_assigned_name as business_unit_assigned_name,
    w.organizational_unit_business_unit_home_code as business_unit_home_code,
    w.organizational_unit_business_unit_home_name as business_unit_home_name,
    w.organizational_unit_cost_number_assigned_name as cost_number_assigned_code,
    w.organizational_unit_cost_number_assigned_name_short_name
    as cost_number_assigned_name,
    w.organizational_unit_cost_number_home_name as cost_number_home_code,
    w.organizational_unit_cost_number_home_name_short_name as cost_number_home_name,
    w.organizational_unit_department_assigned_code as department_assigned_code,
    w.organizational_unit_department_assigned_name as department_assigned_name,
    w.organizational_unit_department_home_code as department_home_code,
    w.organizational_unit_department_home_name as department_home_name,

    w.additional_remuneration_effective_date,
    w.additional_remuneration_rate_amount_value,
    w.additional_remuneration_name_short_name as additional_remuneration_name,

    p.preferred_salutation_legal_name,

    p.person_preferred_name_given_name as preferred_name_given_name,
    p.person_preferred_name_middle_name as preferred_name_middle_name,
    p.person_preferred_name_family_name as preferred_name_family_name,
    p.person_preferred_name_lastfirst as preferred_name_lastfirst,

    p.person_legal_name_given_name as legal_name_given_name,
    p.person_legal_name_middle_name as legal_name_middle_name,
    p.person_legal_name_family_name_1 as legal_name_family_name,
    p.person_legal_name_formatted_name as legal_name_formatted_name,
    p.person_legal_name_nick_name as legal_name_nick_name,
    p.person_legal_name_generation_affix as legal_name_generation_affix,
    p.person_legal_name_qualification_affix as legal_name_qualification_affix,

    p.person_birth_name_family_name_1 as birth_name_family_name,

    p.person_legal_address_line_one as legal_address_line_one,
    p.person_legal_address_line_two as legal_address_line_two,
    p.person_legal_address_line_three as legal_address_line_three,
    p.person_legal_address_city_name as legal_address_city_name,
    p.person_legal_address_country_code as legal_address_country_code,
    p.person_legal_address_country_subdivision_level_1
    as legal_address_country_subdivision_level_1,
    p.person_legal_address_country_subdivision_level_2
    as legal_address_country_subdivision_level_2,
    p.person_legal_address_postal_code as legal_address_postal_code,

    p.person_birth_date as birth_date,
    p.person_ethnicity_long_name as ethnicity_long_name,
    p.person_gender_long_name as gender_long_name,
    p.person_highest_education_level_long_name as highest_education_level_long_name,
    p.person_marital_status_effective_date as marital_status_effective_date,
    p.person_military_discharge_date as military_discharge_date,
    p.person_marital_status_short_name as marital_status_short_name,
    p.person_military_status_long_name as military_status_long_name,
    p.person_race_long_name as race_long_name,
    p.person_race_ethnicity_reporting as race_ethnicity_reporting,
    p.person_tobacco_user_indicator as tobacco_user_indicator,
    p.person_disabled_indicator as disabled_indicator,

    p.disability_long_name as disability,

    p.communication_business_email,
    p.communication_business_landline,
    p.communication_business_mobile,
    p.communication_person_email,
    p.communication_person_landline,
    p.communication_person_mobile,

    p.person_custom_covid_19_booster_1_date as custom_covid_19_booster_1_date,
    p.person_custom_covid_19_booster_1_type as custom_covid_19_booster_1_type,
    p.person_custom_covid_19_date_of_last_vaccine
    as custom_covid_19_date_of_last_vaccine,
    p.person_custom_covid_19_vaccine_type as custom_covid_19_vaccine_type,

    rt.person_preferred_name_given_name as report_to_preferred_name_given_name,
    rt.person_preferred_name_family_name as report_to_preferred_name_family_name,
    rt.person_preferred_name_lastfirst as report_to_preferred_name_lastfirst,
from {{ ref("int_adp_workforce_now__worker") }} as w
inner join
    {{ ref("int_adp_workforce_now__person") }} as p
    on w.work_assignment_worker_id = p.person_worker_id
left join
    {{ ref("int_adp_workforce_now__person") }} as rt
    on w.reports_to_worker_id__id_value = rt.person_worker_id
