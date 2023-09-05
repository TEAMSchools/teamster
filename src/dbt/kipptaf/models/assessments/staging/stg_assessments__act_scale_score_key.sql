select * from {{ source("assessments", "src_assessments__act_scale_score_key") }}
