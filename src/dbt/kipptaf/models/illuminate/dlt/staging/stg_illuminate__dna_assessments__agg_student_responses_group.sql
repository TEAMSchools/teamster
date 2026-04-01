select
    * replace (
        cast(points as numeric) as points,
        cast(points_possible as numeric) as points_possible,
        cast(percent_correct as numeric) as percent_correct,
        cast(raw_score as numeric) as raw_score,
        cast(raw_score_possible as numeric) as raw_score_possible
    ),
from {{ source("illuminate_dna_assessments", "agg_student_responses_group") }}
where points_possible > 0
