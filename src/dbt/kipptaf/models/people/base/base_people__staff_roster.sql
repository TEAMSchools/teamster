with
    -- trunk-ignore(sqlfluff/ST03)
    staff_roster_active as (
        select *,
        from {{ ref("base_people__staff_roster_history") }}
        where work_assignment__fivetran_active
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="staff_roster_active",
                partition_by="employee_number",
                order_by="is_prestart desc, primary_indicator desc, work_assignment_end_date desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select *,
from deduplicate
