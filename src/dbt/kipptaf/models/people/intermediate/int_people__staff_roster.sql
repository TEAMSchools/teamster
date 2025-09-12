with
    -- trunk-ignore(sqlfluff/ST03)
    staff_roster_active as (
        select srh.*,
        from {{ ref("int_people__staff_roster_history") }} as srh
        where srh.primary_indicator and (srh.is_current_record or srh.is_prestart)
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

select
    d.*,

    epm.memberships,
    epm.is_leader_development_program,
    epm.is_teacher_development_program,
from deduplicate as d
left join
    {{ ref("int_adp_workforce_now__employee_memberships") }} as epm
    on d.worker_id = epm.associate_id
    and epm.is_current
