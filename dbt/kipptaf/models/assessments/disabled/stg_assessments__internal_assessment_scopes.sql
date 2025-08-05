select *,
from {{ source("assessments", "src_assessments__internal_assessment_scopes") }}
