{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_pearson", "stg_pearson__student_test_update"),
            source("kippcamden_pearson", "stg_pearson__student_test_update"),
        ]
    )
}}
