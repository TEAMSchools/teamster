select student_id, section_id, school_id,
from {{ source("kipptaf_extracts", "rpt_parentsquare__rosters") }}
where code_location = '{{ project_name }}'
