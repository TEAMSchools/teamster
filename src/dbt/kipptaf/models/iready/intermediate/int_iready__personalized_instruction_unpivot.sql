{{
    dbt_utils.union_relations(
        relations=[
            source("kippnj_iready", "int_iready__personalized_instruction_unpivot"),
            source(
                "kippmiami_iready", "int_iready__personalized_instruction_unpivot"
            ),
        ]
    )
}}
