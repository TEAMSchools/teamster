{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_titan", model.name),
        ]
    )
}}
