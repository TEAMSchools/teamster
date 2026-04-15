with
    work_assignments as (
        select
            wa.associate_oid,
            wa.item_id,
            wa.position_id,
            wa.primary_indicator,
            wa.management_position_indicator,
            wa.voluntary_indicator,
            wa.full_time_equivalence_ratio,
            wa.payroll_file_number,
            wa.payroll_group_code,
            wa.payroll_schedule_group_id,
            wa.hire_date,
            wa.actual_start_date,
            wa.seniority_date,
            wa.termination_date,
            wa.pay_cycle_code__code_value,
            wa.standard_hours__hours_quantity,
            wa.standard_hours__unit_code__code_value,
            wa.standard_pay_period_hours__hours_quantity,
            wa.wage_law_coverage__coverage_code__code_value,
            wa.wage_law_coverage__coverage_code__name,
            wa.wage_law_coverage__wage_law_name_code__code_value,
            wa.wage_law_coverage__wage_law_name_code__name,
            wa.worker_time_profile__badge_id,
            wa.worker_time_profile__time_and_attendance_indicator,
            wa.worker_time_profile__time_zone_code,
            wa.worker_time_profile__time_service_supervisor__associate_oid,
            wa.worker_time_profile__time_service_supervisor__position_id,
            wa.worker_time_profile__time_service_supervisor__worker_id__id_value,
        from {{ ref("int_adp_workforce_now__workers__work_assignments") }} as wa
        where wa.is_current_record
    )

select
    {{ dbt_utils.generate_surrogate_key(["wa.item_id"]) }} as work_assignment_key,

    {{ dbt_utils.generate_surrogate_key(["en.employee_number"]) }} as staff_key,

    en.employee_number,
    wa.item_id,
    wa.position_id,
    wa.primary_indicator,
    wa.management_position_indicator,
    wa.voluntary_indicator,
    wa.full_time_equivalence_ratio,
    wa.payroll_file_number,
    wa.payroll_group_code,
    wa.payroll_schedule_group_id,
    wa.hire_date,
    wa.actual_start_date,
    wa.seniority_date,
    wa.termination_date,
    wa.pay_cycle_code__code_value,
    wa.standard_hours__hours_quantity,
    wa.standard_hours__unit_code__code_value,
    wa.standard_pay_period_hours__hours_quantity,
    wa.wage_law_coverage__coverage_code__code_value,
    wa.wage_law_coverage__coverage_code__name,
    wa.wage_law_coverage__wage_law_name_code__code_value,
    wa.wage_law_coverage__wage_law_name_code__name,
    wa.worker_time_profile__badge_id,
    wa.worker_time_profile__time_and_attendance_indicator,
    wa.worker_time_profile__time_zone_code,
    wa.worker_time_profile__time_service_supervisor__associate_oid,
    wa.worker_time_profile__time_service_supervisor__position_id,
    wa.worker_time_profile__time_service_supervisor__worker_id__id_value,
from work_assignments as wa
left join
    {{ ref("stg_people__employee_numbers") }} as en
    on wa.associate_oid = en.adp_associate_id
