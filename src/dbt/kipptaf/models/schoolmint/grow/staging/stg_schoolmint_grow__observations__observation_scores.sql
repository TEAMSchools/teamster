select
    o.observation_id,

    os.lastmodified as last_modified,
    os.measurement,
    os.measurementgroup as measurement_group,
    os.percentage,
    os.valuescore as value_score,
    os.valuetext as value_text,

    {# repeated records #}
    os.textboxes as text_boxes,
    os.checkboxes,
from {{ ref("stg_schoolmint_grow__observations") }} as o
cross join unnest(o.observation_scores) as os
