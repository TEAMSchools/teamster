{{
    dbt_utils.union_relations(
        relations=[
            source("kipppaterson_powerschool", "stg_powerschool__student_email"),
        ]
    )
}}
