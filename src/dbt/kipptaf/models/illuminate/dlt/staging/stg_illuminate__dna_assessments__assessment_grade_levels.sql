select
    assessment_grade_level_id,
    assessment_id,
    grade_level_id,

    grade_level_id - 1 as grade_level,
from {{ source("illuminate_dna_assessments", "assessment_grade_levels") }}
