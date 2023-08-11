select assessment_grade_level_id, assessment_id, grade_level_id,
from {{ source("illuminate", "assessment_grade_levels") }}
where not _fivetran_deleted
