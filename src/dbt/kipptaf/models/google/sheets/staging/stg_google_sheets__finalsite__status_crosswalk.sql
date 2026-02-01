select
    * except (academic_year),

    academic_year as sre_academic_year,

    cast(enrollment_academic_year as string)
    || '-'
    || right(
        cast(enrollment_academic_year + 1 as string), 2
    ) as enrollment_academic_year_display,

    date(enrollment_academic_year - 1, 10, 16) as sre_academic_year_start,
    date(enrollment_academic_year, 10, 15) as sre_academic_year_end,

from {{ source("google_sheets", "src_google_sheets__finalsite__status_crosswalk") }}
