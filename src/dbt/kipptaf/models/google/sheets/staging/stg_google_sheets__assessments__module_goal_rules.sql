select region, module_type, discipline, grade_min, grade_max, goal, goal_offset,
from {{ source("google_sheets", "src_google_sheets__assessments__module_goal_rules") }}
where region is not null
