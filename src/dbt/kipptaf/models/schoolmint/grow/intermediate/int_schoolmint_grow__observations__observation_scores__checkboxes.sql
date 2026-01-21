select oos.observation_id, oos.measurement, osc.label, osc.value,
from {{ ref("stg_schoolmint_grow__observations__observation_scores") }} as oos
cross join unnest(oos.checkboxes) as osc
