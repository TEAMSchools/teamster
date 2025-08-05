{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__category_grades"),
            source("kippcamden_powerschool", "int_powerschool__category_grades"),
            source("kippmiami_powerschool", "int_powerschool__category_grades"),
        ]
    )
}}
