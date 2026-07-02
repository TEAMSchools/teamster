select id, profile_id, key, created_at, updated_at,
from {{ source("focus", "permission") }}
