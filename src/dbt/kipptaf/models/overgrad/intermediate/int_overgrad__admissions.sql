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

select ur.*, u.*,
from union_relations as ur
inner join {{ ref("stg_overgrad__universities") }} as u on ur.university__id = u.id
