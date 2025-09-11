with
    -- trunk-ignore(sqlfluff/ST03)
    staff_roster_active as (
        select
            srh.*,
            epm.memberships,
            epm.is_in_leadership_program,
            epm.is_in_teacher_program,
        from {{ ref("int_people__staff_roster_history") }} as srh
        left join
            {{ ref("int_people__employee_program_memberships") }} as epm
            on srh.worker_id = epm.associate_id
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
    
-- trunk-ignore(sqlfluff/AM04)
select d.*,
from deduplicate as d
