select *,
from {{ source("illuminate_dna_assessments", "students_assessments_responses") }}
