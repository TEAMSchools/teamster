{% set source_table = source("illuminate", "agg_student_responses_standard") %}

with
    source as (
        select *
        from {{ source_table }}
        where
            points_possible > 0
            and student_assessment_id not in (
                select student_assessment_id
                from {{ source("illuminate", "students_assessments_archive") }}
            )
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="source",
                partition_by="student_assessment_id, standard_id",
                order_by="_fivetran_synced desc",
            )
        }}
    )

select
    {{
        dbt_utils.star(
            from=source_table,
            except=["_fivetran_id", "_fivetran_deleted", "_fivetran_synced"],
        )
    }},
from deduplicate
