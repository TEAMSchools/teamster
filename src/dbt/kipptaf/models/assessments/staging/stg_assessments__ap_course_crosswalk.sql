select *, from {{ source("assessments", "src_assessments__ap_course_crosswalk") }}
