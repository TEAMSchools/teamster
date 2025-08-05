{{
    dbt_utils.union_relations(
        relations=[
            source("kippmiami_fldoe", "int_fldoe__fast_standard_performance_unpivot")
        ]
    )
}}
