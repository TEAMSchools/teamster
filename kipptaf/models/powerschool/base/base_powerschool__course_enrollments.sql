{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "base_powerschool__course_enrollments"),
            source("kippcamden_powerschool", "base_powerschool__course_enrollments"),
            source("kippmiami_powerschool", "base_powerschool__course_enrollments"),
        ]
    )
}}
