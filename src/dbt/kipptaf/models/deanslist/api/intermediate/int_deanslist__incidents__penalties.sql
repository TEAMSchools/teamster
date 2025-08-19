{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "int_deanslist__incidents__penalties"),
            source("kippcamden_deanslist", "int_deanslist__incidents__penalties"),
            source("kippmiami_deanslist", "int_deanslist__incidents__penalties"),
        ]
    )
}}
