{%- set ref_staff_history = ref("base_people__staff_roster_history") -%}

with
    staff_roster_active as (  -- noqa: ST03
        select *, from {{ ref_staff_history }} where work_assignment__fivetran_active
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

select
    {{
        dbt_utils.star(
            from=ref_staff_history,
            except=[
                "work_assignment_start_date",
                "work_assignment_end_date",
                "work_assignment__fivetran_active",
            ],
        )
    }}
from deduplicate
