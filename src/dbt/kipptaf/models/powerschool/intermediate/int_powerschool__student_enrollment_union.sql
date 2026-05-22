with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select
    *,

    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

    initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
from unioned
