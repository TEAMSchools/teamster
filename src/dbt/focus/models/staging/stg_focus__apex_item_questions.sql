select id, item_id, question_id, sort_order, created_at, updated_at,
from {{ source("focus", "apex_item_questions") }}
