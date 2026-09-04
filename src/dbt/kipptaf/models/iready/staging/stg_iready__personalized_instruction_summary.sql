with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnj_iready",
                        "stg_iready__personalized_instruction_summary",
                    ),
                    source(
                        "kippmiami_iready",
                        "stg_iready__personalized_instruction_summary",
                    ),
                ]
            )
        }}
    ),

    sourced as (
        select
            * except (student_id),

            {{
                focus_student_number(
                    "student_id", "academic_year_int", extract_source_project()
                )
            }} as student_id,
        from union_relations
    )

select *,
from sourced
