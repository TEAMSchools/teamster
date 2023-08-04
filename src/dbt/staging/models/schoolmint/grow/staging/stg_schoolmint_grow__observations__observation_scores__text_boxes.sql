select oos.observation_id, oos.measurement, ostb.key, ostb.value,
from {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as oos
cross join unnest(oos.text_boxes) as ostb
