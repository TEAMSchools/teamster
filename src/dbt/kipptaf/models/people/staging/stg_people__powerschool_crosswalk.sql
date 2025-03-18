select employee_number, adp_worker_id, powerschool_teacher_number, `name`, is_active,
from {{ source("people", "src_people__powerschool_crosswalk") }}
