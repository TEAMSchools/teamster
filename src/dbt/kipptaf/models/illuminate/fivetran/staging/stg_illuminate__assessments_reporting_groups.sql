select
    assessment_reporting_group_id,
    assessment_id,
    reporting_group_id,
    performance_band_set_id,
    sort_order,
from {{ source("illuminate", "assessments_reporting_groups") }}
where not _fivetran_deleted
