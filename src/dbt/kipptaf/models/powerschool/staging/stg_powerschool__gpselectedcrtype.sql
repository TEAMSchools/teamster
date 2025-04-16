{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gpselectedcrtype"),
            source("kippcamden_powerschool", "stg_powerschool__gpselectedcrtype"),
        ]
    )
}}
