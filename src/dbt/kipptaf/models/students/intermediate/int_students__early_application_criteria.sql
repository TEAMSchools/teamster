select
    g.criterion_code,
    g.criterion_sort,
    g.gpa_band,
    g.criterion_label,
    g.required_type,
    g.type_label,
    g.urm_bar,
    g.required_count,
    g.requires_full_need,
    g.sets_aside_full_need,

    b.band_sort,
from {{ ref("stg_google_sheets__kfwd__early_apps_goals") }} as g
inner join
    {{ ref("int_students__early_application_gpa_bands") }} as b
    on g.gpa_band = b.gpa_band
