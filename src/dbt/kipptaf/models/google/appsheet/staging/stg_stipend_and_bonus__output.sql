select * except (edited_at), coalesce(edited_at, timestamp_seconds(0)) as edited_at,
from {{ source("google_appsheet", "src_stipend_bonus_app__output") }}
