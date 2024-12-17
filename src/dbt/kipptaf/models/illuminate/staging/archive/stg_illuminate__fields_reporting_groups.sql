select field_id, reporting_group_id,
from {{ source("illuminate", "fields_reporting_groups") }}
where not _fivetran_deleted
