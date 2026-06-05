with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippcamden_powerschool", "stg_powerschool__u_expectations"
                    ),
                    source(
                        "kippnewark_powerschool", "stg_powerschool__u_expectations"
                    ),
                ]
            )
        }}
    )

select *, {{ extract_code_location("union_relations") }} as _dbt_source_project,
from union_relations
