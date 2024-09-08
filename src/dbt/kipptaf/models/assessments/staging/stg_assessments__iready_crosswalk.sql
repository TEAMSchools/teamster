select
    *,
    safe_cast(grade_level as string) as grade_level_string,
    case
        when destination_system = 'FL' and sublevel_number >= 6
        then true
        when destination_system = 'NJSLA' and sublevel_number >= 4
        then true
        else false
    end as is_proficient,
from {{ source("assessments", "src_assessments__iready_crosswalk") }}
