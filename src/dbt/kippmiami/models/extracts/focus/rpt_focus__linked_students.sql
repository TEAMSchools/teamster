select primary_student_id, secondary_student_id,
from {{ source("kipptaf_extracts", "rpt_focus__linked_students") }}
