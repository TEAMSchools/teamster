select
    field_id,
    repository_id,
    `name`,
    label,
    seq,
    `type`,
    calculation,
    `values`,
    expression_id,
    created_at,
    updated_at,
from {{ source("illuminate_dna_repositories", "repository_fields") }}
where deleted_at is null
