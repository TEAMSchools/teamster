select
    *,

    case
        when grade_level >= 9
        then 'HS'
        when grade_level >= 5
        then 'MS'
        when grade_level >= 0
        then 'ES'
    end as school_level,

from {{ source("google_sheets", "src_google_sheets__finalsite__school_scaffold") }}
