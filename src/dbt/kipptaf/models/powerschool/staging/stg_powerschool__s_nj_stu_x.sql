with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__s_nj_stu_x"),
                    source("kippcamden_powerschool", "stg_powerschool__s_nj_stu_x"),
                    source("kipppaterson_powerschool", "stg_powerschool__s_nj_stu_x"),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *, regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
