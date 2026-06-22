select id, syear, school_id, title, code, created_at, updated_at,
from {{ source("focus", "report_card_comments") }}
