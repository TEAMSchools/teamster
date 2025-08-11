{{
    dbt_utils.union_relations(
        relations=[
            source(
                "kippnewark_powerschool", "int_powerschool__category_grades_pivot"
            ),
            source(
                "kippcamden_powerschool", "int_powerschool__category_grades_pivot"
            ),
            source("kippmiami_powerschool", "int_powerschool__category_grades_pivot"),
        ]
    )
}}
