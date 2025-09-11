with
    -- trunk-ignore(sqlfluff/ST03)
    staff_roster_active as (
        select *,
        from {{ ref("int_people__staff_roster_history") }}
        where primary_indicator and (is_current_record or is_prestart)
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="staff_roster_active",
                partition_by="employee_number",
                order_by="effective_date_start desc",
            )
        }}
    )

select d.*, epm.memberships, epm.is_in_leadership_program, epm.is_in_teacher_program,
from deduplicate as d
left join
    {{ ref("int_people__employee_program_memberships") }} as epm
    on d.worker_id = epm.associate_id
where epm.is_in_leadership_program or epm.is_in_teacher_program
