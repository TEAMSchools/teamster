with
    -- trunk-ignore(sqlfluff/ST03)
    source as (
        select * except (_fivetran_id, _fivetran_deleted),
        from {{ source("illuminate", "agg_student_responses_standard") }}
        where
            points_possible > 0
            and student_assessment_id not in (
                select saa.student_assessment_id,
                from {{ source("illuminate", "students_assessments_archive") }} as saa
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

-- trunk-ignore(sqlfluff/AM04)
select *,
from deduplicate
