{{
    dbt_utils.union_relations(
        relations=[
            source("kippnj_iready", "stg_iready__instruction_by_lesson_pro"),
            source("kippmiami_iready", "stg_iready__instruction_by_lesson_pro"),
        ]
    )
}}
