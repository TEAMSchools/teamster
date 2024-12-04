{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "stg_deanslist__incidents__attachments"),
            source("kippcamden_deanslist", "stg_deanslist__incidents__attachments"),
            source("kippmiami_deanslist", "stg_deanslist__incidents__attachments"),
        ]
    )
}}
