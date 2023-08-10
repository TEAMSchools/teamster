select assessment_id, standard_id, performance_band_set_id,
from {{ source("illuminate", "assessment_standards") }}
where not _fivetran_deleted
