select
    field_id,
    repository_id,
    name,
    label,
    seq,
    type,
    calculation,
    `values`,
    expression_id,
    created_at,
    updated_at,
from {{ source("illuminate", "repository_fields") }}
where not _fivetran_deleted and deleted_at is null
