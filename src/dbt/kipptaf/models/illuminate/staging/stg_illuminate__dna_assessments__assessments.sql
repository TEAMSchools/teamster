select *,
from {{ source("illuminate_dna_assessments", "assessments") }}
where deleted_at is null
