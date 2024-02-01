select *, safe_cast(grade_level as string) as grade_level_string,
from {{ source("assessments", "src_assessments__iready_crosswalk") }}
