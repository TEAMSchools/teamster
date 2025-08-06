with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    )

select u.*, if(l.name is null, true, false) as is_transfer_grade,
from union_relations as u
left join {{ ref("stg_people__location_crosswalk") }} as l on u.schoolname = l.name
