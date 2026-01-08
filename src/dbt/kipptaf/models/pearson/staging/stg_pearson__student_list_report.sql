{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_pearson", "stg_pearson__student_list_report"),
            source("kippcamden_pearson", "stg_pearson__student_list_report"),
            source("kipppaterson_pearson", "stg_pearson__student_list_report"),
        ]
    )
}}
