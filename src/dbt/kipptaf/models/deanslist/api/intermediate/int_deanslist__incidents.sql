{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", "int_deanslist__incidents"),
            source("kippcamden_deanslist", "int_deanslist__incidents"),
            source("kippmiami_deanslist", "int_deanslist__incidents"),
        ]
    )
}}
