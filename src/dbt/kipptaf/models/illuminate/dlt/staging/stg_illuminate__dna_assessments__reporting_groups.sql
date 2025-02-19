select reporting_group_id, label,
from {{ source("illuminate_dna_assessments", "reporting_groups") }}
