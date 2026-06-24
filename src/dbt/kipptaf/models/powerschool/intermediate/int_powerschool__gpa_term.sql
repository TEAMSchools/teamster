with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "int_powerschool__gpa_term"),
                    source("kippcamden_powerschool", "int_powerschool__gpa_term"),
                    source("kippmiami_powerschool", "int_powerschool__gpa_term"),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
