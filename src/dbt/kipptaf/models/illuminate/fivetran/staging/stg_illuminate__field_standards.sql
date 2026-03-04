select field_id, standard_id,
from {{ source("illuminate", "field_standards") }}
where not _fivetran_deleted
