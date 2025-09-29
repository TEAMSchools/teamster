select
    * except (academic_year, adp_title),

    cast(academic_year as int) as academic_year,

    trim(adp_title) as adp_title,

    concat(academic_year, '_', staffing_model_id) as surrogate_key,
from {{ source("google_appsheet", "src_seat_tracker__seats") }}
