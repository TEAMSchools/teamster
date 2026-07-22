with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                    source("kipppaterson_powerschool", model.name),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
