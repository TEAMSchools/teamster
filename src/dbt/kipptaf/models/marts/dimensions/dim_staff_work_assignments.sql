with
    work_assignments as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_adp_workforce_now__workers__work_assignments"),
                partition_by="item_id",
                order_by="effective_date_start desc",
            )
        }}
    ),

    workers as (
        select associate_oid, worker_id__id_value,
        from {{ ref("stg_adp_workforce_now__workers") }}
        where is_current_record
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
        sup_en.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["sup_en.employee_number"]) }},
        cast(null as string)
    ) as time_approver_staff_key,

    wa.position_id,
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

    if(
        wa.actual_start_date <= current_date('{{ var("local_timezone") }}')
        and (
            wa.termination_date is null
            or wa.termination_date >= current_date('{{ var("local_timezone") }}')
        ),
        true,
        false
    ) as is_current,
from work_assignments as wa
left join workers as w on wa.associate_oid = w.associate_oid
left join employee_numbers as en on w.worker_id__id_value = en.adp_associate_id
left join
    workers as sup_w
    on wa.worker_time_profile__time_service_supervisor__associate_oid
    = sup_w.associate_oid
left join
    employee_numbers as sup_en on sup_w.worker_id__id_value = sup_en.adp_associate_id
