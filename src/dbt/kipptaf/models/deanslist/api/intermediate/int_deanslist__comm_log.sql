with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__comm_log"),
                    source("kippcamden_deanslist", "int_deanslist__comm_log"),
                    source("kippmiami_deanslist", "int_deanslist__comm_log"),
                    source("kipppaterson_deanslist", "int_deanslist__comm_log"),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
