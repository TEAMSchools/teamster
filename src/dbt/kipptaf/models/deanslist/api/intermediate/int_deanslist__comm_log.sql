with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__comm_log"),
                    source("kippcamden_deanslist", "int_deanslist__comm_log"),
                    source("kippmiami_deanslist", "int_deanslist__comm_log"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    if(reason like 'Att:%', true, false) as is_attendance_call,
    if(reason like 'Chronic Absence:%', true, false) as is_truancy_call,
from union_relations
