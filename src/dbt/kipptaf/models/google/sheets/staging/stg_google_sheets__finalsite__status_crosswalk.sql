with
    transformations as (
        select
            *,

            if(
                enrollment_year_extract = 'Next_Year',
                {{ var("current_academic_year") + 1 }},
                {{ var("current_academic_year") }}
            ) as enrollment_academic_year,

        from
            {{
                source(
                    "google_sheets", "src_google_sheets__finalsite__status_crosswalk"
                )
            }}
    )

select
    *,

    cast(enrollment_academic_year as string)
    || '-'
    || right(
        cast(enrollment_academic_year + 1 as string), 2
    ) as enrollment_academic_year_display,

    date(enrollment_academic_year - 1, 10, 16) as sre_academic_year_start,

    date(enrollment_academic_year, 6, 30) as sre_academic_year_end,

from transformations
