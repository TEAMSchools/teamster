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
                partition_by="associate_oid",
                order_by="is_prestart desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select *,
from deduplicate
