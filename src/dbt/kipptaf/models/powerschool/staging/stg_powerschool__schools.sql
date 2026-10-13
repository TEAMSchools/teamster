with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__schools"),
                    source("kippcamden_powerschool", "stg_powerschool__schools"),
                    source("kipppaterson_powerschool", "stg_powerschool__schools"),
                ]
            )
        }}
    )

select u.*, {{ extract_source_project("u") }} as _dbt_source_project,
from unioned as u
