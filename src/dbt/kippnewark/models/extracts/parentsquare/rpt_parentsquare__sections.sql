select section_id, school_id, staff_id, section_number, is_primary, course_name,
from {{ source("kipptaf_extracts", "rpt_parentsquare__sections") }}
where code_location = '{{ project_name }}'
