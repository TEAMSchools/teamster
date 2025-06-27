select *, from {{ source("google_sheets", "src_google_sheets__dibels_goals_long") }}
