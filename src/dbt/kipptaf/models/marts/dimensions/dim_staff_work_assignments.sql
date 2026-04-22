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
        from {{ ref("int_adp_workforce_now__workers__work_assignments") }} as wa
        where wa.is_current_record
    ),

    employee_numbers as (
        select employee_number, adp_associate_id,
        from {{ ref("stg_people__employee_numbers") }}
        where is_active
    )

select
    {{ dbt_utils.generate_surrogate_key(["wa.item_id"]) }} as work_assignment_key,

    if(
        en.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["en.employee_number"]) }},
        cast(null as string)
    ) as staff_key,

    if(
        sup.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["sup.employee_number"]) }},
        cast(null as string)
    ) as time_service_supervisor_staff_key,

    wa.position_id,
    wa.primary_indicator as is_primary_position,
    wa.management_position_indicator as is_management_position,
    wa.voluntary_indicator as is_voluntary_termination,
    wa.full_time_equivalence_ratio as full_time_equivalency,
    wa.payroll_file_number,
    wa.payroll_group_code,
    wa.hire_date,
    wa.actual_start_date,
    wa.seniority_date,
    wa.termination_date,
    wa.pay_cycle_code__code_value as pay_cycle_code,
    wa.standard_hours__hours_quantity as standard_hours,
    wa.standard_hours__unit_code__code_value as standard_hours_unit_code,
    wa.standard_pay_period_hours__hours_quantity as standard_pay_period_hours,
    wa.wage_law_coverage__coverage_code__code_value as wage_law_coverage_code,
    wa.wage_law_coverage__coverage_code__name as wage_law_coverage_name,
    wa.wage_law_coverage__wage_law_name_code__code_value as wage_law_code,
    wa.wage_law_coverage__wage_law_name_code__name as wage_law_name,
    wa.worker_time_profile__badge_id as time_badge_id,
    wa.worker_time_profile__time_and_attendance_indicator
    as is_time_and_attendance_active,
    wa.worker_time_profile__time_zone_code as time_zone_code,
from work_assignments as wa
left join employee_numbers as en on wa.associate_oid = en.adp_associate_id
left join
    employee_numbers as sup
    on wa.worker_time_profile__time_service_supervisor__associate_oid
    = sup.adp_associate_id
