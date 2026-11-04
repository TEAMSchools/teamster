select student_id, school_id, grade_level, first_name, last_name, `status`,
from {{ source("kipptaf_extracts", "rpt_parentsquare__students") }}
where code_location = '{{ project_name }}'
