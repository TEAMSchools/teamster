{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "stg_deanslist__behavior"),
            source("kippcamden_deanslist", "stg_deanslist__behavior"),
            source("kippmiami_deanslist", "stg_deanslist__behavior"),
        ]
    )
}}
