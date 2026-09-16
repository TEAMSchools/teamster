with
    row_numbered as (
        select
            student_assessment_id,
            student_id,
            assessment_id,
            date_taken,
            created_at,
            updated_at,
            version_id,

            row_number() over (
                partition by student_id, assessment_id
                order by updated_at desc, student_assessment_id desc
            ) as rn,
        from {{ source("illuminate_dna_assessments", "students_assessments") }}
    )

select
    student_assessment_id,
    student_id,
    assessment_id,
    date_taken,
    created_at,
    updated_at,
    version_id,
from row_numbered
where rn = 1
