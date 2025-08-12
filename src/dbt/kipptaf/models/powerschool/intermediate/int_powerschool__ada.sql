{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "int_powerschool__ada"),
            source("kippcamden_powerschool", "int_powerschool__ada"),
            source("kippmiami_powerschool", "int_powerschool__ada"),
        ]
    )
}}
