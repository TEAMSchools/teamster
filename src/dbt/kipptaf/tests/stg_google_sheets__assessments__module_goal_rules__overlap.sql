select
    a.region,
    a.module_type,
    a.discipline as discipline_a,
    a.grade_min as grade_min_a,
    a.grade_max as grade_max_a,

    b.discipline as discipline_b,
    b.grade_min as grade_min_b,
    b.grade_max as grade_max_b,
from {{ ref("stg_google_sheets__assessments__module_goal_rules") }} as a
inner join
    {{ ref("stg_google_sheets__assessments__module_goal_rules") }} as b
    on a.region = b.region
    and a.module_type = b.module_type
    and a.grade_min <= b.grade_max
    and a.grade_max >= b.grade_min
    and (a.discipline = b.discipline or a.discipline is null or b.discipline is null)
    -- one direction per pair
    and (
        a.grade_min < b.grade_min
        or (
            a.grade_min = b.grade_min
            and coalesce(a.discipline, '') < coalesce(b.discipline, '')
        )
    )
