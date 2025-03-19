select *, from {{ source("assessments", "src_assessments__course_subject_crosswalk") }}
