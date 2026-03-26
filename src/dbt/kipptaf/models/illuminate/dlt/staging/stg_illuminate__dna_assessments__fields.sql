select *,
from {{ source("illuminate_dna_assessments", "fields") }}
where deleted_at is null
