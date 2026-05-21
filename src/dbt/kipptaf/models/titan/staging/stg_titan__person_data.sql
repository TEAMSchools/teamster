with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_titan", "stg_titan__person_data"),
                    source("kippcamden_titan", "stg_titan__person_data"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
