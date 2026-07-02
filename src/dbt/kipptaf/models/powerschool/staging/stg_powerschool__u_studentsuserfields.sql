with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "stg_powerschool__u_studentsuserfields",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "stg_powerschool__u_studentsuserfields",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "stg_powerschool__u_studentsuserfields",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "stg_powerschool__u_studentsuserfields",
                    ),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
