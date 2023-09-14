{{
    dbt_utils.union_relations(
        relations=[
            source("kippmiami_fldoe", model.name)
        ]
    )
}}
