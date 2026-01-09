with
    distinct_rows as (
        select distinct * except (enrollment_type),
        from {{ source("finalsite", "status_report") }}
    ),

    transformations as (
        select
            * except (powerschool_student_number, `timestamp`, grade_level),

            grade_level as grade_level_name,

            cast(powerschool_student_number as int) as powerschool_student_number,

            cast(`timestamp` as date) as status_start_date,

            cast(left(enrollment_year, 4) as int) as academic_year,

            initcap(replace(`status`, '_', ' ')) as detailed_status,

            if(
                grade_level = 'Kindergarten',
                0,
                cast(regexp_extract(grade_level, r'\d+') as int)
            ) as grade_level,

        from distinct_rows
    )

select
    *,

    coalesce(
        lead(status_start_date - 1) over (
            partition by academic_year, finalsite_student_id order by status_start_date
        ),
        current_date('America/New_York')
    ) as status_end_date,

from transformations
