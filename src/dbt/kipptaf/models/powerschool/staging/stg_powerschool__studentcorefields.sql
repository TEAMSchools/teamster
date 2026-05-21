with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool", "stg_powerschool__studentcorefields"
                    ),
                    source(
                        "kippcamden_powerschool", "stg_powerschool__studentcorefields"
                    ),
                    source(
                        "kippmiami_powerschool", "stg_powerschool__studentcorefields"
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "stg_powerschool__studentcorefields",
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
