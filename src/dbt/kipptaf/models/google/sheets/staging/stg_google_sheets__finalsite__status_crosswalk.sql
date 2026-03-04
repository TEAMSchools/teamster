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

from transformations
