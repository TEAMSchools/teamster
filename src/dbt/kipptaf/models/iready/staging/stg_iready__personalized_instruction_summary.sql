{{
    dbt_utils.union_relations(
        relations=[
            source("kippnj_iready", "stg_iready__personalized_instruction_summary"),
            source(
                "kippmiami_iready", "stg_iready__personalized_instruction_summary"
            ),
        ]
    )
}}
