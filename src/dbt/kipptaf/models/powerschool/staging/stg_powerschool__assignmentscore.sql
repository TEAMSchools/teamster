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

-- trunk-ignore(sqlfluff/AM04)
select *, {{ extract_code_location("union_relations") }} as _dbt_source_project,
from union_relations
