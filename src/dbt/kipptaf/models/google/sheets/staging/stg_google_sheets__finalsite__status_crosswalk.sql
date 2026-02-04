select
    *,

    cast(enrollment_academic_year as string)
    || '-'
    || right(
        cast(enrollment_academic_year + 1 as string), 2
    ) as enrollment_academic_year_display,

from {{ source("google_sheets", "src_google_sheets__finalsite__status_crosswalk") }}
