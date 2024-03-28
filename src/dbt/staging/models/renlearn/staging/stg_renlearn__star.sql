{{
    dbt_utils.union_relations(
        relations=[
            source("kippnj_renlearn", model.name),
            source("kippmiami_renlearn", model.name),
        ]
    )
}}
