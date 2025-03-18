select
    powerschool_course_number,
    powerschool_course_name,
    illuminate_subject_area,
    is_foundations,
    is_advanced_math,
    exclude_from_gradebook,
    duplicate_audit,
from {{ source("assessments", "src_assessments__course_subject_crosswalk") }}
