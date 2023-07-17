select
    oos.observation_id,

    ostb.key as observation_score_text_box_key,
    ostb.value as observation_score_text_box_value,
from {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as oos
cross join unnest(oos.observation_score_text_boxes) as ostb
