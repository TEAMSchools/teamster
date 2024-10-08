{{
    dbt_utils.union_relations(
        relations=[
            source("kippnj_iready", model.name),
            source("kippmiami_iready", model.name),
        ]
    )
}}
