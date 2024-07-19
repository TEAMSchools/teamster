select *, from {{ source("google_appsheet", "src_seat_tracker__seats") }}
