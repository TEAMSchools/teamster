select
    *,

    case
        bm_period when 'MOY' then 'BOY->MOY' when 'EOY' then 'MOY->EOY'
    end as matching_pm_season,

    if(grade = 'K', 0, safe_cast(grade as int64)) as grade_level,

from {{ source("google_sheets", "src_google_sheets__dibels_goals_long") }}
