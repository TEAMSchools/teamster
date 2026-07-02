select
    id, standard_id, course_num, school_id, district_id, cpalms, created_at, updated_at,
from {{ source("focus", "standards_join_courses") }}
