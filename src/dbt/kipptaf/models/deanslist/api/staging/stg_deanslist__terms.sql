{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "stg_deanslist__terms"),
            source("kippcamden_deanslist", "stg_deanslist__terms"),
            source("kippmiami_deanslist", "stg_deanslist__terms"),
        ]
    )
}}
