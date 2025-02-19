with
    source as (
        select
            student_assessment_id,
            student_id,
            assessment_id,
            date_taken,
            created_at,
            updated_at,
            version_id,
        from {{ source("illuminate", "students_assessments") }}
        where not _fivetran_deleted
    )

    {{
        dbt_utils.deduplicate(
            relation="source",
            partition_by="student_id, assessment_id",
            order_by="updated_at desc",
        )
    }}
