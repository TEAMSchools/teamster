select *,
from {{ source("illuminate", "assessment_fields") }}
where not _fivetran_deleted
