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
                    source(
                        "kipppaterson_powerschool", "stg_powerschool__u_expectations"
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
