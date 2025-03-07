{{
    dbt_utils.union_relations(
        relations=[source("kippmiami_fldoe", "int_fldoe__fte_pivot")]
    )
}}
