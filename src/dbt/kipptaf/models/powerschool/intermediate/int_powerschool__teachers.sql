{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__teachers"),
            source("kippcamden_powerschool", "int_powerschool__teachers"),
            source("kippmiami_powerschool", "int_powerschool__teachers"),
        ]
    )
}}
