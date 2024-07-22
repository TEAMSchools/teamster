select
    * except (edited_at), parse_datetime('%m/%d/%Y %H:%M:%S', edited_at) as edited_at,
from {{ source("google_appsheet", "src_seat_tracker__seats") }}
where academic_year is not null
