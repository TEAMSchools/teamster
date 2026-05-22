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

-- _dbt_source_project is required by dim_student_meal_eligibility_status for per-stint
-- joins; materialized here so downstream consumers can join without re-deriving it from
-- _dbt_source_relation.
-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
