{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__teacher_grade_levels"),
            source("kippcamden_powerschool", "int_powerschool__teacher_grade_levels"),
            source("kippmiami_powerschool", "int_powerschool__teacher_grade_levels"),
        ]
    )
}}
