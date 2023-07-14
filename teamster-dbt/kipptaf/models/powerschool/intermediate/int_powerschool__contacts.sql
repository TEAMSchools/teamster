{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__contacts"),
            source("kippcamden_powerschool", "int_powerschool__contacts"),
            source("kippmiami_powerschool", "int_powerschool__contacts"),
        ]
    )
}}
