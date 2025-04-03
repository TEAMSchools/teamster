with
    students_assessments as (
        select
            student_assessment_id,
            student_id,
            assessment_id,
            date_taken,
            created_at,
            updated_at,
            version_id,
        from {{ source("illuminate_dna_assessments", "students_assessments") }}
    )

    {{
        dbt_utils.deduplicate(
            relation="students_assessments",
            partition_by="student_id, assessment_id",
            order_by="updated_at desc, student_assessment_id desc",
        )
    }}
