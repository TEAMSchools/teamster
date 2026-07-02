with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__s_nj_ren_x"),
                    source("kippcamden_powerschool", "stg_powerschool__s_nj_ren_x"),
                    source("kipppaterson_powerschool", "stg_powerschool__s_nj_ren_x"),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
