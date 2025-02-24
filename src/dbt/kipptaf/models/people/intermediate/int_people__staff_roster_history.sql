with
    adp_df_union as (
        select
            '{{ ref("int_adp_workforce_now__workers") }}' as _dbt_source_relation,

            w.associate_oid,
            w.effective_date_end,
            w.effective_date_end_timestamp,
            w.is_current_record,
            w.worker_id__id_value as worker_id,
            w.worker_dates__original_hire_date as worker_original_hire_date,
            w.worker_dates__rehire_date as worker_rehire_date,
            w.worker_dates__termination_date as worker_termination_date,
            w.worker_status__status_code__code_value as worker_status_code,
            w.work_assignment__termination_date as work_assignment_termination_date,
            w.work_assignment__actual_start_date as work_assignment_actual_start_date,
            w.person__formatted_name as formatted_name,
            w.person__family_name_1 as family_name_1,
            w.person__given_name as given_name,
            w.person__legal_name__formatted_name as legal_formatted_name,
            w.person__legal_name__family_name_1 as legal_family_name,
            w.person__legal_name__given_name as legal_given_name,
            w.person__birth_date as birth_date,
            w.person__race_code_name as race_code,
            w.person__ethnicity_code_name as ethnicity_code,
            w.person__gender_code_name as gender_code,
            w.person__legal_address__city_name as legal_address_city_name,
            w.person__legal_address__country_subdivision_level_1__code_value
            as legal_address_country_subdivision_level_1_code,
            w.person__legal_address__line_one as legal_address_line_one,
            w.person__legal_address__postal_code as legal_address_postal_code,
            w.is_prestart,
            w.item_id,
            w.position_id,
            w.job_title,
            w.primary_indicator,
            w.management_position_indicator,
            w.assignment_status__status_code__name as assignment_status,
            w.assignment_status__status_code__name__lag as assignment_status_lag,
            w.assignment_status__effective_date as assignment_status_effective_date,
            w.assignment_status__reason_code__name as assignment_status_reason,
            w.home_work_location__name_code__name as home_work_location_name,
            w.worker_type_code__name as worker_type_code,
            w.wage_law_coverage__wage_law_name_code__name as wage_law_name,
            w.wage_law_coverage__coverage_code__name as wage_law_coverage,
            w.base_remuneration__annual_rate_amount__amount_value
            as base_remuneration_annual_rate_amount,
            w.base_remuneration__hourly_rate_amount__amount_value
            as base_remuneration_hourly_rate_amount,
            w.additional_remunerations__rate__amount_value__sum
            as additional_remunerations_rate_amount,
            w.communication__personal_cell__formatted_number as personal_cell,
            w.communication__personal_email__email_uri as personal_email,
            w.communication__work_cell__formatted_number as work_cell,
            w.communication__work_email__email_uri as work_email,
            w.custom_field__employee_number,
            w.wf_mgr_accrual_profile,
            w.wf_mgr_badge_number,
            w.wf_mgr_ee_type,
            w.wf_mgr_pay_rule,
            w.wf_mgr_trigger,
            w.organizational_unit__assigned__business_unit__code_value
            as assigned_business_unit_code,
            w.organizational_unit__assigned__business_unit__name
            as assigned_business_unit_name,
            w.organizational_unit__assigned__department__name
            as assigned_department_name,
            w.organizational_unit__home__business_unit__code_value
            as home_business_unit_code,
            w.organizational_unit__home__business_unit__name as home_business_unit_name,
            w.organizational_unit__home__department__name as home_department_name,
            w.reports_to_worker_id__id_value as reports_to_worker_id,
            w.reports_to_formatted_name,
            w.payroll_file_number,
            w.payroll_group_code,
            w.benefits_eligibility_class__group_code__name
            as benefits_eligibility_class,
            w.worker_hire_date_recent,
            w.wf_mgr_trigger_new,

            en.employee_number,

            null as race_ethnicity_reporting,
            null as reports_to_employee_number,

            if(
                w.effective_date_start < '2021-01-01',
                '2021-01-01',
                w.effective_date_start
            ) as effective_date_start,

            if(
                w.effective_date_start_timestamp
                < timestamp('2021-01-01', '{{ var("local_timezone") }}'),
                timestamp('2021-01-01', '{{ var("local_timezone") }}'),
                w.effective_date_start_timestamp
            ) as effective_date_start_timestamp,
        from {{ ref("int_adp_workforce_now__workers") }} as w
        inner join
            {{ ref("stg_people__employee_numbers") }} as en
            on w.worker_id__id_value = en.adp_associate_id
            and en.is_active
        /* after transistion from Dayforce */
        where w.effective_date_end >= '2021-01-01'

        union all

        select
            '{{ ref("int_dayforce__employee_history") }}' as _dbt_source_relation,
            null as associate_oid,

            effective_end_date as effective_date_end,
            effective_end_timestamp as effective_date_end_timestamp,

            false as is_current_record,
            null as worker_id,

            original_hire_date as worker_original_hire_date,
            rehire_date as worker_rehire_date,
            termination_date as worker_termination_date,

            null as worker_status_code,
            null as work_assignment_termination_date,

            work_assignment_effective_start_date as work_assignment_actual_start_date,
            preferred_name_lastfirst as formatted_name,
            preferred_last_name as family_name_1,
            preferred_first_name as given_name,

            null as legal_formatted_name,

            legal_last_name as legal_family_name,
            legal_first_name as legal_given_name,
            birth_date,

            null as race_code,

            ethnicity as ethnicity_code,
            gender as gender_code,
            city as legal_address_city_name,
            `state` as legal_address_country_subdivision_level_1_code,
            `address` as legal_address_line_one,
            postal_code as legal_address_postal_code,
            false as is_prestart,
            surrogate_key as item_id,

            null as position_id,

            job_name as job_title,
            true as primary_indicator,

            null as management_position_indicator,

            `status` as assignment_status,

            null as assignment_status_lag,

            status_effective_start_date as assignment_status_effective_date,
            status_reason_description as assignment_status_reason,
            physical_location_name as home_work_location_name,
            pay_class_name as worker_type_code,

            'Fair Labor Standards Act' as wage_law_name,

            flsa_status_name as wage_law_coverage,
            base_salary as base_remuneration_annual_rate_amount,

            null as base_remuneration_hourly_rate_amount,

            null as additional_remunerations_rate_amount,

            mobile_number as personal_cell,

            null as personal_email,
            null as work_cell,
            null as work_email,
            null as custom_field__employee_number,
            null as wf_mgr_accrual_profile,
            null as wf_mgr_badge_number,
            null as wf_mgr_ee_type,
            null as wf_mgr_pay_rule,
            null as wf_mgr_trigger,
            null as assigned_business_unit_code,

            legal_entity_name as assigned_business_unit_name,
            department_name as assigned_department_name,

            null as home_business_unit_code,

            legal_entity_name as home_business_unit_name,
            department_name as home_department_name,

            null as reports_to_worker_id,
            null as reports_to_formatted_name,
            null as payroll_file_number,
            null as payroll_group_code,
            null as benefits_eligibility_class,
            null as worker_hire_date_recent,
            null as wf_mgr_trigger_new,

            employee_number,
            race_ethnicity_reporting,
            manager_employee_number as reports_to_employee_number,
            effective_start_date as effective_date_start,
            effective_start_timestamp as effective_date_start_timestamp,
        from {{ ref("int_dayforce__employee_history") }}
    )

select
    w._dbt_source_relation,
    w.associate_oid,
    w.worker_id,
    w.employee_number,
    w.effective_date_start,
    w.effective_date_end,
    w.effective_date_start_timestamp,
    w.effective_date_end_timestamp,
    w.is_current_record,
    w.worker_original_hire_date,
    w.worker_rehire_date,
    w.worker_termination_date,
    w.worker_status_code,
    w.work_assignment_termination_date,
    w.work_assignment_actual_start_date,
    w.formatted_name,
    w.family_name_1,
    w.given_name,
    w.legal_formatted_name,
    w.legal_family_name,
    w.legal_given_name,
    w.birth_date,
    w.race_code,
    w.ethnicity_code,
    w.gender_code,
    w.legal_address_city_name,
    w.legal_address_country_subdivision_level_1_code,
    w.legal_address_line_one,
    w.legal_address_postal_code,
    w.is_prestart,
    w.item_id,
    w.position_id,
    w.job_title,
    w.primary_indicator,
    w.management_position_indicator,
    w.assignment_status,
    w.assignment_status_lag,
    w.assignment_status_effective_date,
    w.assignment_status_reason,
    w.home_work_location_name,
    w.worker_type_code,
    w.wage_law_name,
    w.wage_law_coverage,
    w.base_remuneration_annual_rate_amount,
    w.additional_remunerations_rate_amount,
    w.personal_cell,
    w.personal_email,
    w.work_cell,
    w.work_email,
    w.custom_field__employee_number,
    w.wf_mgr_accrual_profile,
    w.wf_mgr_badge_number,
    w.wf_mgr_ee_type,
    w.wf_mgr_pay_rule,
    w.wf_mgr_trigger,
    w.wf_mgr_trigger_new,
    w.assigned_business_unit_code,
    w.assigned_business_unit_name,
    w.assigned_department_name,
    w.home_business_unit_code,
    w.home_business_unit_name,
    w.home_department_name,
    w.reports_to_worker_id,
    w.reports_to_formatted_name,
    w.payroll_file_number,
    w.payroll_group_code,
    w.benefits_eligibility_class,
    w.worker_hire_date_recent,

    lc.location_region as home_work_location_region,
    lc.location_dagster_code_location as home_work_location_dagster_code_location,
    lc.location_clean_name as home_work_location_reporting_name,
    lc.location_abbreviation as home_work_location_abbreviation,
    lc.location_grade_band as home_work_location_grade_band,
    lc.location_reporting_school_id as home_work_location_reporting_school_id,
    lc.location_powerschool_school_id as home_work_location_powerschool_school_id,
    lc.location_deanslist_school_id as home_work_location_deanslist_school_id,
    lc.location_is_campus as home_work_location_is_campus,
    lc.location_is_pathways as home_work_location_is_pathways,
    lc.location_head_of_schools_employee_number
    as home_work_location_head_of_schools_employee_number,
    lc.campus_name as home_work_location_campus_name,
    lc.head_of_schools_sam_account_name,

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

    lower(ldap.sam_account_name) as sam_account_name,
    lower(ldap.user_principal_name) as user_principal_name,
    lower(ldap.mail) as mail,

    lower(rtldap.sam_account_name) as reports_to_sam_account_name,
    lower(rtldap.user_principal_name) as reports_to_user_principal_name,
    lower(rtldap.mail) as reports_to_mail,

    coalesce(
        idps.powerschool_teacher_number, cast(w.employee_number as string)
    ) as powerschool_teacher_number,

    coalesce(
        w.reports_to_employee_number, rten.employee_number
    ) as reports_to_employee_number,

    coalesce(
        sis.race_ethnicity_reporting, w.race_ethnicity_reporting
    ) as race_ethnicity_reporting,

    case
        when coalesce(sis.gender_identity, w.gender_code) = 'Female'
        then 'Cis Woman'
        when coalesce(sis.gender_identity, w.gender_code) = 'Male'
        then 'Cis Man'
        else coalesce(sis.gender_identity, w.gender_code)
    end as gender_identity,

    case
        when contains_substr(sis.race_ethnicity, 'Latinx/Hispanic/Chicana(o)')
        then true
        when w.ethnicity_code = 'Hispanic or Latino'
        then true
        else false
    end as is_hispanic,
from adp_df_union as w
left join
    {{ ref("stg_people__employee_numbers") }} as rten
    on w.reports_to_worker_id = rten.adp_associate_id
    and rten.is_active
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on w.home_work_location_name = lc.location_name
left join
    {{ ref("stg_ldap__user_person") }} as ldap
    on w.employee_number = ldap.employee_number
left join
    {{ ref("stg_people__powerschool_crosswalk") }} as idps
    on w.employee_number = idps.employee_number
    and idps.is_active
left join
    {{ ref("int_surveys__staff_information_survey_pivot") }} as sis
    on w.employee_number = sis.employee_number
left join
    {{ ref("stg_ldap__user_person") }} as rtldap
    on coalesce(w.reports_to_employee_number, rten.employee_number)
    = rtldap.employee_number
