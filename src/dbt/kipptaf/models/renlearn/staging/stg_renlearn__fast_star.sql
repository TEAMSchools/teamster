{{
    dbt_utils.union_relations(
        relations=[source("kippmiami_renlearn", "stg_renlearn__fast_star")]
    )
}}
