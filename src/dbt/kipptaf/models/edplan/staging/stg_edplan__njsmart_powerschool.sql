{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_edplan", model.name),
            source("kippcamden_edplan", model.name),
        ]
    )
}}
