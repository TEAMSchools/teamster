select
    * except (grade_level),

    -- -1 in the sheet means "whole-school total"; recoded to -9 so -1 can
    -- mean PK everywhere downstream (PK = -1, K = 0, 1-12).
    if(grade_level = -1, -9, grade_level) as grade_level,

    case
        when grade_level >= 9
        then 'HS'
        when grade_level >= 5
        then 'MS'
        when grade_level >= 0
        then 'ES'
    end as school_level,

from {{ source("google_sheets", "src_google_sheets__finalsite__school_scaffold") }}
