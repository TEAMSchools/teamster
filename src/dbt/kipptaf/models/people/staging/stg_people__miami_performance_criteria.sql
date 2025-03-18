select
    academic_year,
    criteria,
    grade_level,
    `group` as criteria_group,
    measure,
    payout_amount,
from {{ source("people", "src_people__miami_performance_criteria") }}
