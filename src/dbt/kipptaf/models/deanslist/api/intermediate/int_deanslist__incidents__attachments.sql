with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_deanslist",
                        "int_deanslist__incidents__attachments",
                    ),
                    source(
                        "kippcamden_deanslist",
                        "int_deanslist__incidents__attachments",
                    ),
                    source(
                        "kippmiami_deanslist", "int_deanslist__incidents__attachments"
                    ),
                    source(
                        "kipppaterson_deanslist",
                        "int_deanslist__incidents__attachments",
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, {{ extract_source_project() }} as _dbt_source_project,
from union_relations
