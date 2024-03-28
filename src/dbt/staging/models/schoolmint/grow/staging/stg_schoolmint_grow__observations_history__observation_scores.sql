select
    o.observation_id,
    o.last_modified_date,
    o.last_modified_date_lead,

    os.measurement,
    os.measurementgroup as measurement_group,
    os.percentage as `percentage`,
    os.valuescore as value_score,
    os.valuetext as value_text,

    {# repeated records #}
    os.textboxes as text_boxes,
    os.checkboxes as checkboxes,
from {{ ref("stg_schoolmint_grow__observations_history") }} as o
cross join unnest(o.observation_scores) as os
