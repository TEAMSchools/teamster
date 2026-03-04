{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "int_deanslist__incidents__attachments"),
            source("kippcamden_deanslist", "int_deanslist__incidents__attachments"),
            source("kippmiami_deanslist", "int_deanslist__incidents__attachments"),
        ]
    )
}}
