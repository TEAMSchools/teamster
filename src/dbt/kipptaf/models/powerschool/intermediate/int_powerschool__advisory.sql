{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__advisory"),
            source("kippcamden_powerschool", "int_powerschool__advisory"),
            source("kippmiami_powerschool", "int_powerschool__advisory"),
        ]
    )
}}
