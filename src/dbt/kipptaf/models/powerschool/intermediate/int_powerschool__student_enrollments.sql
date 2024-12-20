with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__student_enrollments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__student_enrollments",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__student_enrollments",
                    ),
                ]
            )
        }}
    ),

    parse_region as (
        -- trunk-ignore(sqlfluff/AM04)
        select *, regexp_extract(_dbt_source_relation, r'kipp(\w+)_') as region,
        from union_relations
    )

select * except (region), initcap(region) as region, 'kipp' || region as code_location,
from parse_region
