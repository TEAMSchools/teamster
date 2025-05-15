select * except (`group`), `group` as criteria_group,
from {{ source("people", "src_people__miami_performance_criteria") }}
