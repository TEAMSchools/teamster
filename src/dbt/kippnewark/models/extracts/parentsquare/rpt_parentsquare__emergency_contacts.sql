select contact_id, student_id, school_id, first_name, last_name, phone, email,
from {{ source("kipptaf_extracts", "rpt_parentsquare__emergency_contacts") }}
where code_location = '{{ project_name }}'
