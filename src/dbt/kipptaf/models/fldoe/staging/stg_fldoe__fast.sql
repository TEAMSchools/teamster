{{
    dbt_utils.union_relations(
        relations=[source("kippmiami_fldoe", "stg_fldoe__fast")]
    )
}}
