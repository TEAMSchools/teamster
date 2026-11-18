with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__incidents"),
                    source("kippcamden_deanslist", "int_deanslist__incidents"),
                    source("kippmiami_deanslist", "int_deanslist__incidents"),
                    source("kipppaterson_deanslist", "int_deanslist__incidents"),
                ]
            )
        }}
    )

select u.*, {{ extract_source_project("u") }} as _dbt_source_project,
from union_relations as u
