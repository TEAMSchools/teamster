select
    * except (grade_level),

    -- -1 in the sheet means "whole-school total"; recoded to -9 (see
    -- stg_google_sheets__finalsite__school_scaffold).
    if(grade_level = -1, -9, grade_level) as grade_level,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
