select staff_id, school_id, email, title, first_name, last_name,
from {{ source("kipptaf_extracts", "rpt_parentsquare__staff") }}
where code_location = '{{ project_name }}'
