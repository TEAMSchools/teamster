{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__gpa_term"),
            source("kippcamden_powerschool", "int_powerschool__gpa_term"),
            source("kippmiami_powerschool", "int_powerschool__gpa_term"),
        ]
    )
}}
