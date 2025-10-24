select *,
from {{ source("google_appsheet", "src_google_appsheet__seat_tracker__people") }}
