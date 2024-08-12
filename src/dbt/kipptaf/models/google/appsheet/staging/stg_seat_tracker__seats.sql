select * except (academic_year), cast(academic_year as int) as academic_year,
from {{ source("google_appsheet", "src_seat_tracker__seats") }}
