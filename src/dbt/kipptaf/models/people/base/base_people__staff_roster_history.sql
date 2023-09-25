with
    worker_person as (
        select
            work_assignment__fivetran_start,
            work_assignment__fivetran_end,
            work_assignment__fivetran_active,
            work_assignment_id,
            work_assignment_worker_id as worker_id,
            work_assignment_actual_start_date,
            work_assignment_hire_date,
            work_assignment_termination_date,
            work_assignment_assignment_status_long_name as assignment_status,
            work_assignment_assignment_status_long_name_prev as assignment_status_prev,
            ifnull(
                work_assignment_assignment_status_reason_long_name,
                work_assignment_assignment_status_reason_short_name
            ) as assignment_status_reason,
            work_assignment_assignment_status_effective_date
            as assignment_status_effective_date,
            work_assignment_management_position_indicator
            as management_position_indicator,
            work_assignment_payroll_processing_status_short_name
            as payroll_processing_status_short_name,
            work_assignment_payroll_group_code as payroll_group_code,
            work_assignment_payroll_file_number as payroll_file_number,
            work_assignment_payroll_schedule_group_id as payroll_schedule_group_id,
            work_assignment_position_id as position_id,
            work_assignment_primary_indicator as primary_indicator,
            work_assignment_pay_cycle_short_name as pay_cycle_short_name,
            ifnull(
                work_assignment_home_work_location_name_long_name,
                work_assignment_home_work_location_name_short_name
            ) as home_work_location_name,
            work_assignment_job_title as job_title,
            work_assignment_wage_law_coverage_name_long_name
            as wage_law_coverage_name_long_name,
            work_assignment_wage_law_coverage_short_name
            as wage_law_coverage_short_name,
            work_assignment_seniority_date,
            ifnull(
                work_assignment_worker_type_long_name,
                work_assignment_worker_type_short_name
            ) as worker_type,
            work_assignment_standard_pay_period_hour_hours_quantity
            as standard_pay_period_hour_hours_quantity,
            work_assignment_standard_hour_hours_quantity
            as standard_hour_hours_quantity,
            work_assignment_standard_hour_unit_short_name
            as standard_hour_unit_short_name,
            work_assignment_full_time_equivalence_ratio as full_time_equivalence_ratio,
            work_assignment_custom_payroll_custom_area_1
            as custom_payroll_custom_area_1,
            work_assignment_custom_payroll_custom_area_2
            as custom_payroll_custom_area_2,
            work_assignment_custom_payroll_custom_area_3
            as custom_payroll_custom_area_3,
            work_assignment_custom_payroll_data_control as custom_payroll_data_control,

            worker_associate_oid as associate_oid,
            worker_status_value as status_value,
            worker_original_hire_date,
            worker_rehire_date,
            worker_termination_date,
            worker_custom_nj_pension_number as custom_nj_pension_number,
            worker_custom_employee_number as custom_employee_number,
            worker_custom_wfmgr_accrual_profile as custom_wfmgr_accrual_profile,
            worker_custom_wfmgr_badge_number as custom_wfmgr_badge_number,
            worker_custom_wfmgr_ee_type as custom_wfmgr_ee_type,
            worker_custom_wfmgr_home_hyperfind as custom_wfmgr_home_hyperfind,
            worker_custom_wfmgr_loa_return_date as custom_wfmgr_loa_return_date,
            worker_custom_wfmgr_loa as custom_wfmgr_loa,
            worker_custom_wfmgr_pay_rule as custom_wfmgr_pay_rule,
            worker_custom_wfmgr_trigger as custom_wfmgr_trigger,
            safe_cast(
                worker_custom_miami_aces_number as int
            ) as custom_miami_aces_number,

            preferred_salutation_legal_name,
            person_legal_name_given_name as legal_name_given_name,
            person_legal_name_middle_name as legal_name_middle_name,
            person_legal_name_family_name_1 as legal_name_family_name,
            person_legal_name_formatted_name as legal_name_formatted_name,
            person_legal_name_nick_name as legal_name_nick_name,
            person_legal_name_generation_affix as legal_name_generation_affix,
            person_legal_name_qualification_affix as legal_name_qualification_affix,
            ifnull(
                person_preferred_name_given_name, person_legal_name_given_name
            ) as preferred_name_given_name,
            ifnull(
                person_preferred_name_middle_name, person_legal_name_middle_name
            ) as preferred_name_middle_name,
            ifnull(
                person_preferred_name_family_name_1, person_legal_name_family_name_1
            ) as preferred_name_family_name,
            person_birth_name_family_name_1 as birth_name_family_name,
            person_legal_address_line_one as legal_address_line_one,
            person_legal_address_line_two as legal_address_line_two,
            person_legal_address_line_three as legal_address_line_three,
            person_legal_address_city_name as legal_address_city_name,
            person_legal_address_country_code as legal_address_country_code,
            person_legal_address_country_subdivision_level_1
            as legal_address_country_subdivision_level_1,
            person_legal_address_country_subdivision_level_2
            as legal_address_country_subdivision_level_2,
            person_legal_address_postal_code as legal_address_postal_code,
            person_birth_date as birth_date,
            person_gender_long_name as gender_long_name,
            person_ethnicity_long_name as ethnicity_long_name,
            person_race_long_name as race_long_name,
            person_marital_status_short_name as marital_status_short_name,
            person_marital_status_effective_date as marital_status_effective_date,
            person_military_status_long_name as military_status_long_name,
            person_military_discharge_date as military_discharge_date,
            person_highest_education_level_long_name
            as highest_education_level_long_name,
            person_tobacco_user_indicator as tobacco_user_indicator,
            person_disabled_indicator as disabled_indicator,
            person_custom_covid_19_booster_1_date as custom_covid_19_booster_1_date,
            person_custom_covid_19_booster_1_type as custom_covid_19_booster_1_type,
            person_custom_covid_19_date_of_last_vaccine
            as custom_covid_19_date_of_last_vaccine,
            person_custom_covid_19_vaccine_type as custom_covid_19_vaccine_type,

            disability_long_name as disability,

            ifnull(
                organizational_unit_business_unit_assigned_name_long_name,
                organizational_unit_business_unit_assigned_name_short_name
            ) as business_unit_assigned_name,
            organizational_unit_business_unit_assigned_name
            as business_unit_assigned_code,
            ifnull(
                organizational_unit_business_unit_home_name_long_name,
                organizational_unit_business_unit_home_name_short_name
            ) as business_unit_home_name,
            organizational_unit_business_unit_home_name as business_unit_home_code,
            organizational_unit_cost_number_assigned_name_short_name
            as cost_number_assigned_name,
            organizational_unit_cost_number_assigned_name as cost_number_assigned_code,
            organizational_unit_cost_number_home_name_short_name
            as cost_number_home_name,
            organizational_unit_cost_number_home_name as cost_number_home_code,
            ifnull(
                organizational_unit_department_assigned_name_long_name,
                organizational_unit_department_assigned_name_short_name
            ) as department_assigned_name,
            organizational_unit_department_assigned_name as department_assigned_code,
            ifnull(
                organizational_unit_department_home_name_long_name,
                organizational_unit_department_home_name_short_name
            ) as department_home_name,
            organizational_unit_department_home_name as department_home_code,

            base_remuneration_effective_date,
            base_remuneration_annual_rate_amount_amount_value,

            additional_remuneration_effective_date,
            additional_remuneration_rate_amount_value,
            additional_remuneration_name_short_name as additional_remuneration_name,

            communication_person_email,
            communication_person_mobile,
            communication_business_email,

            group_name_long_name as worker_group_name,
            ifnull(group_group_long_name, group_group_short_name) as worker_group_value,

            report_to_id as report_to_associate_oid,
            report_to_position_id,
            report_to_report_to_worker_id as report_to_worker_id,

            communication_person_landline,
            communication_business_mobile,
            communication_business_landline,
        from {{ ref("base_adp_workforce_now__worker_person") }}
        where not worker__fivetran_deleted
    ),

    with_prestart as (
        select *, false as is_prestart
        from worker_person
        where
            assignment_status_effective_date
            <= current_date('{{ var("local_timezone") }}')

        union all

        select *, true as is_prestart,
        from worker_person
        where
            assignment_status_effective_date
            > current_date('{{ var("local_timezone") }}')
            and assignment_status = 'Active'
            and (
                assignment_status_prev is null or assignment_status_prev = 'Terminated'
            )
    ),

    crosswalk as (
        select
            wp.*,
            wp.preferred_name_family_name
            || ', '
            || wp.preferred_name_given_name as preferred_name_lastfirst,

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

            en.employee_number,

            ldap.mail,
            ldap.distinguished_name,
            ldap.user_principal_name,
            ldap.sam_account_name,
            ldap.physical_delivery_office_name,
            ldap.uac_account_disable,

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

            case
                when coalesce(sis.gender_identity, wp.gender_long_name) = 'Female'
                then 'Cis Woman'
                when coalesce(sis.gender_identity, wp.gender_long_name) = 'Male'
                then 'Cis Man'
                else coalesce(sis.gender_identity, wp.gender_long_name)
            end as gender_identity,

            case
                when regexp_contains(sis.race_ethnicity, 'Latinx/Hispanic/Chicana(o)')
                then true
                when wp.ethnicity_long_name = 'Hispanic or Latino'
                then true
                else false
            end as is_hispanic,

            coalesce(
                case
                    when regexp_contains(sis.race_ethnicity, 'I decline to state')
                    then 'Decline to State'
                    when sis.race_ethnicity = 'Latinx/Hispanic/Chicana(o)'
                    then 'Latinx/Hispanic/Chicana(o)'
                    when sis.race_ethnicity = 'My racial/ethnic identity is not listed'
                    then 'Race/Ethnicity Not Listed'
                    when regexp_contains(sis.race_ethnicity, 'Bi/Multiracial')
                    then 'Bi/Multiracial'
                    when regexp_contains(sis.race_ethnicity, ',')
                    then 'Bi/Multiracial'
                    else sis.race_ethnicity
                end,
                case
                    wp.race_long_name
                    when 'Black or African American'
                    then 'Black/African American'
                    when 'Hispanic or Latino'
                    then 'Latinx/Hispanic/Chicana(o)'
                    when 'Two or more races (Not Hispanic or Latino)'
                    then 'Bi/Multiracial'
                    else wp.race_long_name
                end
            ) as race_ethnicity_reporting,

            regexp_replace(
                lower(ldap.user_principal_name),
                r'^([\w-\.]+@)[\w-]+(\.+[\w-]{2,4})$',
                if(
                    wp.business_unit_home_name = 'KIPP Miami',
                    r'\1kippmiami\2',
                    r'\1apps.teamschools\2'
                )
            ) as google_email,

            ifnull(
                idps.powerschool_teacher_number, safe_cast(en.employee_number as string)
            ) as powerschool_teacher_number,
        from with_prestart as wp
        left join
            {{ ref("stg_people__location_crosswalk") }} as lc
            on wp.home_work_location_name = lc.name
        inner join
            {{ ref("stg_people__employee_numbers") }} as en
            on wp.worker_id = en.adp_associate_id
            and en.is_active
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

        union all

        select
            safe_cast(
                eh.effective_start_date as timestamp
            ) as work_assignment__fivetran_start,
            safe_cast(
                eh.effective_end_date as timestamp
            ) as work_assignment__fivetran_end,
            eh.is_active as work_assignment__fivetran_active,
            null as work_assignment_id,
            null as worker_id,
            eh.work_assignment_effective_start_date
            as work_assignment_actual_start_date,
            null as work_assignment_hire_date,
            null as work_assignment_termination_date,
            eh.status as assignment_status,
            null as assignment_status_prev,
            eh.status_reason_description as assignment_status_reason,
            eh.status_effective_start_date as assignment_status_effective_date,
            null as management_position_indicator,
            null as payroll_processing_status_short_name,
            null as payroll_group_code,
            null as payroll_file_number,
            null as payroll_schedule_group_id,
            null as position_id,
            null as primary_indicator,
            null as pay_cycle_short_name,
            eh.physical_location_name as home_work_location_name,
            eh.job_name as job_title,
            'Fair Labor Standards Act' as wage_law_coverage_name_long_name,
            eh.flsa_status_name as wage_law_coverage_short_name,
            null as work_assignment_seniority_date,
            eh.pay_class_name as worker_type,
            null as standard_pay_period_hour_hours_quantity,
            null as standard_hour_hours_quantity,
            null as standard_hour_unit_short_name,
            null as full_time_equivalence_ratio,
            null as custom_payroll_custom_area_1,
            null as custom_payroll_custom_area_2,
            null as custom_payroll_custom_area_3,
            null as custom_payroll_data_control,
            null as associate_oid,
            null as status_value,
            eh.original_hire_date as worker_original_hire_date,
            eh.rehire_date as worker_rehire_date,
            eh.termination_date as worker_termination_date,
            null as custom_nj_pension_number,
            null as custom_employee_number,
            null as custom_wfmgr_accrual_profile,
            null as custom_wfmgr_badge_number,
            null as custom_wfmgr_ee_type,
            null as custom_wfmgr_home_hyperfind,
            null as custom_wfmgr_loa_return_date,
            null as custom_wfmgr_loa,
            null as custom_wfmgr_pay_rule,
            null as custom_wfmgr_trigger,
            null as custom_miami_aces_number,
            null as preferred_salutation_legal_name,
            eh.legal_first_name as legal_name_given_name,
            null as legal_name_middle_name,
            eh.legal_last_name as legal_name_family_name,
            null as legal_name_formatted_name,
            null as legal_name_nick_name,
            null as legal_name_generation_affix,
            null as legal_name_qualification_affix,
            eh.preferred_first_name as preferred_name_given_name,
            null as preferred_name_middle_name,
            eh.preferred_last_name as preferred_name_family_name,
            null as birth_name_family_name,
            eh.address as legal_address_line_one,
            null as legal_address_line_two,
            null as legal_address_line_three,
            eh.city as legal_address_city_name,
            null as legal_address_country_code,
            eh.state as legal_address_country_subdivision_level_1,
            null as legal_address_country_subdivision_level_2,
            eh.postal_code as legal_address_postal_code,
            eh.birth_date as birth_date,
            eh.gender as gender_long_name,
            eh.ethnicity as ethnicity_long_name,
            null as race_long_name,
            null as marital_status_short_name,
            null as marital_status_effective_date,
            null as military_status_long_name,
            null as military_discharge_date,
            null as highest_education_level_long_name,
            null as tobacco_user_indicator,
            null as disabled_indicator,
            null as custom_covid_19_booster_1_date,
            null as custom_covid_19_booster_1_type,
            null as custom_covid_19_date_of_last_vaccine,
            null as custom_covid_19_vaccine_type,
            null as disability,
            eh.legal_entity_name as business_unit_assigned_name,
            null as business_unit_assigned_code,
            eh.legal_entity_name as business_unit_home_name,
            null as business_unit_home_code,
            null as cost_number_assigned_name,
            null as cost_number_assigned_code,
            null as cost_number_home_name,
            null as cost_number_home_code,
            eh.department_name as department_assigned_name,
            null as department_assigned_code,
            eh.department_name as department_home_name,
            null as department_home_code,
            null as base_remuneration_effective_date,
            eh.base_salary as base_remuneration_annual_rate_amount_amount_value,
            null as additional_remuneration_effective_date,
            null as additional_remuneration_rate_amount_value,
            null as additional_remuneration_name,
            null as communication_person_email,
            null as communication_person_mobile,
            null as communication_business_email,
            null as worker_group_name,
            null as worker_group_value,
            null as report_to_associate_oid,
            null as report_to_position_id,
            null as report_to_worker_id,
            null as communication_person_landline,
            eh.mobile_number as communication_business_mobile,
            null as communication_business_landline,
            false as is_prestart,
            eh.preferred_last_name
            || ', '
            || eh.preferred_first_name as preferred_name_lastfirst,

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

            eh.employee_number,

            ldap.mail,
            ldap.distinguished_name,
            ldap.user_principal_name,
            ldap.sam_account_name,
            ldap.physical_delivery_office_name,
            ldap.uac_account_disable,

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

            case
                when coalesce(sis.gender_identity, eh.gender) = 'Female'
                then 'Cis Woman'
                when coalesce(sis.gender_identity, eh.gender) = 'Male'
                then 'Cis Man'
                else coalesce(sis.gender_identity, eh.gender)
            end as gender_identity,

            case
                when regexp_contains(sis.race_ethnicity, 'Latinx/Hispanic/Chicana(o)')
                then true
                when eh.ethnicity = 'Hispanic or Latino'
                then true
                else false
            end as is_hispanic,

            coalesce(
                case
                    when regexp_contains(sis.race_ethnicity, 'I decline to state')
                    then 'Decline to State'
                    when sis.race_ethnicity = 'Latinx/Hispanic/Chicana(o)'
                    then 'Latinx/Hispanic/Chicana(o)'
                    when sis.race_ethnicity = 'My racial/ethnic identity is not listed'
                    then 'Race/Ethnicity Not Listed'
                    when regexp_contains(sis.race_ethnicity, 'Bi/Multiracial')
                    then 'Bi/Multiracial'
                    when regexp_contains(sis.race_ethnicity, ',')
                    then 'Bi/Multiracial'
                    else sis.race_ethnicity
                end,
                case
                    eh.ethnicity
                    when 'Black or African American'
                    then 'Black/African American'
                    when 'Hispanic or Latino'
                    then 'Latinx/Hispanic/Chicana(o)'
                    when 'Two or more races (Not Hispanic or Latino)'
                    then 'Bi/Multiracial'
                    else eh.ethnicity
                end
            ) as race_ethnicity_reporting,

            regexp_replace(
                lower(ldap.user_principal_name),
                r'^([\w-\.]+@)[\w-]+(\.+[\w-]{2,4})$',
                if(
                    eh.legal_entity_name = 'KIPP Miami',
                    r'\1kippmiami\2',
                    r'\1apps.teamschools\2'
                )
            ) as google_email,

            ifnull(
                idps.powerschool_teacher_number, safe_cast(eh.employee_number as string)
            ) as powerschool_teacher_number,
        from {{ ref("base_dayforce__employee_history") }} as eh
        left join
            {{ ref("stg_people__location_crosswalk") }} as lc
            on eh.physical_location_name = lc.name
        left join
            {{ ref("stg_ldap__user_person") }} as ldap
            on eh.employee_number = ldap.employee_number
        left join
            {{ ref("stg_people__powerschool_crosswalk") }} as idps
            on eh.employee_number = idps.employee_number
            and idps.is_active
        left join
            {{ ref("int_surveys__staff_information_survey_pivot") }} as sis
            on eh.employee_number = sis.employee_number
    ),

    with_manager as (
        select
            cw.*,

            coalesce(
                ph.preferred_name_given_name, ph.legal_name_given_name
            ) as report_to_preferred_name_given_name,
            coalesce(
                ph.preferred_name_family_name_1, ph.legal_name_family_name_1
            ) as report_to_preferred_name_family_name,
            coalesce(ph.preferred_name_family_name_1, ph.legal_name_family_name_1)
            || ', '
            || coalesce(
                ph.preferred_name_given_name, ph.legal_name_given_name
            ) as report_to_preferred_name_lastfirst,

            en.employee_number as report_to_employee_number,

            ldap.user_principal_name as report_to_user_principal_name,
            ldap.mail as report_to_mail,
            ldap.sam_account_name as report_to_sam_account_name,
        from crosswalk as cw
        left join
            {{ ref("stg_adp_workforce_now__person_history") }} as ph
            on cw.report_to_worker_id = ph.worker_id
        left join
            {{ ref("stg_people__employee_numbers") }} as en
            on cw.report_to_worker_id = en.adp_associate_id
            and en.is_active
        left join
            {{ ref("stg_ldap__user_person") }} as ldap
            on en.employee_number = ldap.employee_number
    )

select wm.*, tgl.grade_level as primary_grade_level_taught
from with_manager as wm
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on wm.powerschool_teacher_number = tgl.teachernumber
    and tgl.academic_year = {{ var("current_academic_year") }}
    and tgl.grade_level_rank = 1
