{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gpselectedcrs"),
            source("kippcamden_powerschool", "stg_powerschool__gpselectedcrs"),
        ]
    )
}}
