select
    * replace(
        cast(points as numeric) as points,
        cast(points_possible as numeric) as points_possible,
        cast(percent_correct as numeric) as percent_correct
    ),
from {{ source("illuminate_dna_assessments", "agg_student_responses_standard") }}
where points_possible > 0
