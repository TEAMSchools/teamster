{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_powerschool", "stg_powerschool__gptarget"),
            source("kippcamden_powerschool", "stg_powerschool__gptarget"),
        ]
    )
}}
