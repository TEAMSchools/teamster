with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__attendance"),
                    source("kippcamden_powerschool", "stg_powerschool__attendance"),
                    source("kippmiami_powerschool", "stg_powerschool__attendance"),
                    source("kipppaterson_powerschool", "stg_powerschool__attendance"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project() }} as _dbt_source_project,
from union_relations
