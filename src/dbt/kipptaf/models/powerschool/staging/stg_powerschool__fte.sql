with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__fte"),
                    source("kippcamden_powerschool", "stg_powerschool__fte"),
                    source("kippmiami_powerschool", "stg_powerschool__fte"),
                    source("kipppaterson_powerschool", "stg_powerschool__fte"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project() }} as _dbt_source_project,
from union_relations
