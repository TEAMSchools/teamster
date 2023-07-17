select
    oos.observation_id,

    osc.label as observation_score_checkbox_label,
    osc.value as observation_score_checkbox_value,
from {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as oos
cross join unnest(oos.observation_score_checkboxes) as osc
