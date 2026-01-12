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
    ),

    end_date_calc as (
        select
            *,

            lead(
                status_start_date - 1,
                1,
                current_date('{{ var("local_timezone") }}')
            ) over (
                partition by finalsite_student_id, enrollment_year
                order by status_start_date asc
            ) as status_end_date,

        from transformations
    )

select *, date_diff(status_end_date, status_start_date, day) as days_in_status,
from end_date_calc
