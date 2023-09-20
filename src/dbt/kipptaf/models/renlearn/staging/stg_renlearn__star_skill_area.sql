{{
    dbt_utils.union_relations(
        relations=[
            source("kippmiami_renlearn", model.name),
        ]
    )
}}
