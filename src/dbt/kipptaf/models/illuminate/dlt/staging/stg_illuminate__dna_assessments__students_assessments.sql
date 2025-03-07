select
    student_assessment_id,
    student_id,
    assessment_id,
    date_taken,
    created_at,
    updated_at,
    version_id,
from {{ source("illuminate_dna_assessments", "students_assessments") }}
