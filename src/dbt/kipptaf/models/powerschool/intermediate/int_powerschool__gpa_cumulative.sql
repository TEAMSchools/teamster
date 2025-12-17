{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__gpa_cumulative"),
            source("kippcamden_powerschool", "int_powerschool__gpa_cumulative"),
            source("kippmiami_powerschool", "int_powerschool__gpa_cumulative"),
        ]
    )
}}
