select
    source_system,
    destination_system,
    test_name,
    grade_level,
    sublevel_name,
    sublevel_number,
    scale_low,
    scale_high,

    cast(grade_level as string) as grade_level_string,

    safe_cast(right(sublevel_name, 1) as int) as `level`,

    case
        when destination_system = 'FL' and sublevel_number >= 6
        then true
        when
            (destination_system = 'NJSLA' or destination_system = 'i-Ready')
            and sublevel_number >= 4
        then true
        else false
    end as is_proficient,
from {{ source("assessments", "src_assessments__iready_crosswalk") }}
