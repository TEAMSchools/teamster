select *,
from {{ source("illuminate_dna_assessments", "agg_student_responses_standard") }}
where points_possible > 0
