{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "stg_deanslist__users"),
            source("kippcamden_deanslist", "stg_deanslist__users"),
            source("kippmiami_deanslist", "stg_deanslist__users"),
        ]
    )
}}
