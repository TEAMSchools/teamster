select *, from {{ source("illuminate_dna_assessments", "field_responses") }}
