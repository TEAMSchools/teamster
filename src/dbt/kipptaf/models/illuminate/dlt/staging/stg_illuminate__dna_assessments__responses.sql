select *, from {{ source("illuminate_dna_assessments", "responses") }}
