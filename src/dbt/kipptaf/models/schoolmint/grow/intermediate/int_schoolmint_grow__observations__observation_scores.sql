select
    o.observation_id,

    os.lastmodified as last_modified,
    os.measurement,
    os.measurementgroup as measurement_group,
    os.percentage,
    os.valuescore as value_score,
    os.valuetext as value_text,

    ostb.key as text_box_key,
    ostb.value as text_box_value,

    regexp_replace(
        regexp_replace(ostb.value, r'<[^>]*>', ''), r'&nbsp;', ' '
    ) as text_box_value_clean,
from {{ ref("stg_schoolmint_grow__observations") }} as o
left join unnest(o.observation_scores) as os
left join unnest(os.textboxes) as ostb
