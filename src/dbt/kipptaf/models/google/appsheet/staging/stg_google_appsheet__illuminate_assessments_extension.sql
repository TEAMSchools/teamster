select
    *,

    grade_level + 1 as illuminate_grade_level_id,

    concat(module_type, module_sequence) as module_code,
from {{ source("google_appsheet", "illuminate_assessments_extension") }}
