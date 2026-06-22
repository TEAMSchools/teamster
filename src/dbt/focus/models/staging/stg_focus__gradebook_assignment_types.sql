select
    assignment_type_id,
    title,
    template_id,
    template_category_id,
    rollover_id,
    copied_from_id,
    external_api_id,
    external_api_uuid,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "gradebook_assignment_types") }}
