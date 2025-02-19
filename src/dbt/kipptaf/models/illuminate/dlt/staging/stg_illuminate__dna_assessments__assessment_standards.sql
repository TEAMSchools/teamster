select assessment_id, standard_id, performance_band_set_id,
from {{ source("illuminate_dna_assessments", "assessment_standards") }}
