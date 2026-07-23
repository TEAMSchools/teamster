with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__s_nj_crs_x"),
                    source("kippcamden_powerschool", "stg_powerschool__s_nj_crs_x"),
                    source("kipppaterson_powerschool", "stg_powerschool__s_nj_crs_x"),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,
from union_relations as ur
