select *, from {{ source("assessments", "src_assessments__student_number_xwalk") }}
