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

-- _dbt_source_project is required by dim_student_ell_status and dim_student_iep_status
-- (Miami/Paterson legs) for per-stint joins; materialized here so downstream consumers
-- can join without re-deriving it from _dbt_source_relation.
-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
