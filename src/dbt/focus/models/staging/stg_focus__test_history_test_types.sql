select id, district_id, title, sort_order, is_default, created_at, updated_at,
from {{ source("focus", "test_history_test_types") }}
