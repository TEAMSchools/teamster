{{
    dbt_utils.union_relations(
        relations=[source("kippmiami_finalsite", "stg_finalsite__status_report")]
    )
}}
