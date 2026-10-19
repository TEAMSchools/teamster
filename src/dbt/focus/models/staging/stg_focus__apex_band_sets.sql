select id, name, is_default, created_at, updated_at,
from {{ source("focus", "apex_band_sets") }}
where deleted is not true
