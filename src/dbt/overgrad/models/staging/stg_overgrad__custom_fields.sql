select
    id,
    created_at,
    updated_at,
    `name`,
    `description`,
    resource_class,
    field_type,
    format,
    student_can_view,
    student_can_edit,
from {{ source("overgrad", "src_overgrad__custom_fields") }}
