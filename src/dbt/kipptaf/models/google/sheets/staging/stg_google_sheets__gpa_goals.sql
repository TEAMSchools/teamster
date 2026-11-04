select
    cast(academic_year as int64) as academic_year,
    cast(org_level as string) as org_level,
    cast(region as string) as region,
    cast(schoolid as int64) as schoolid,
    cast(grade_low as int64) as grade_low,
    cast(grade_high as int64) as grade_high,
    cast(metric as string) as metric,
    cast(threshold as numeric) as threshold,
    cast(direction as string) as direction,
    cast(goal as numeric) as goal,
from {{ source("google_sheets", "src_google_sheets__gpa_goals") }}
where academic_year is not null
