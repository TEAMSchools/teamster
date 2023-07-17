select
    o.observation_id as `observation_id`,

    os.lastmodified as `observation_score_last_modified`,
    os.measurement as `observation_score_measurement`,
    os.measurementgroup as `observation_score_measurement_group`,
    os.percentage as `observation_score_percentage`,
    os.valuescore as `observation_score_value_score`,
    os.valuetext as `observation_score_value_text`,
    os.textboxes as `observation_score_text_boxes`,
    os.checkboxes as `observation_score_checkboxes`,
from {{ ref("stg_schoolmint_grow__observations") }} as o
cross join unnest(o.observation_scores) as os
