select
    id,
    district_id,
    profile,
    title,
    type,
    super_profile,
    description,
    inactive,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "user_profiles") }}
