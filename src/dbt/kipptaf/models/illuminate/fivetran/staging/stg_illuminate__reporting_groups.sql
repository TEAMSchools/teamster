select reporting_group_id, label,
from {{ source("illuminate", "reporting_groups") }}
where not _fivetran_deleted
