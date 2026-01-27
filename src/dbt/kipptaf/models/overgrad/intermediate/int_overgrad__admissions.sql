with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_overgrad", "int_overgrad__admissions"),
                    source("kippcamden_overgrad", "int_overgrad__admissions"),
                ]
            )
        }}
    )

select
    ur.*,

    u.ipeds_id as university_ipeds_id,
    u.name as university_name,
    u.status as university_status,
    u.city as university_city,
    u.state as university_state,
from union_relations as ur
inner join {{ ref("stg_overgrad__universities") }} as u on ur.university__id = u.id
