{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_deanslist", model.name),
            source("kippcamden_deanslist", model.name),
            source("kippmiami_deanslist", model.name),
        ]
    )
}}
