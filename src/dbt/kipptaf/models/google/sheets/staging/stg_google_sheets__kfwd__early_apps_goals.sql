select
    criterion_code,
    criterion_sort,
    gpa_band,
    criterion_label,
    required_type,
    type_label,
    urm_bar,
    required_count,
    requires_full_need,
    sets_aside_full_need,
from {{ source("google_sheets", "src_google_sheets__kfwd__early_apps_goals") }}
where criterion_code is not null
