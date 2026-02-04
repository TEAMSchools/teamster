with
    transformations as (
        select
            * except (
                powerschool_student_number, `timestamp`, grade_level, enrollment_type
            ),

            enrollment_type as enrollment_type_raw,
            grade_level as grade_level_name,

            cast(powerschool_student_number as int) as powerschool_student_number,

            cast(left(enrollment_year, 4) as int) as enrollment_academic_year,

            date(
                cast(`timestamp` as timestamp), '{{ var("local_timezone") }}'
            ) as status_start_date,

            initcap(replace(`status`, '_', ' ')) as detailed_status,

            if(
                grade_level = 'Kindergarten',
                0,
                cast(regexp_extract(grade_level, r'\d+') as int)
            ) as grade_level,
        from {{ source("finalsite", "status_report") }}
    ),

    dedupe as (
        select
            *,

            lag(`status`, 1, '') over (
                partition by finalsite_student_id, enrollment_year
                order by status_start_date asc
            ) as status_lag,

            last_value(school ignore nulls) over (
                partition by enrollment_academic_year, finalsite_student_id
                order by status_start_date asc
                rows between unbounded preceding and unbounded following
            ) as latest_school,

            last_value(powerschool_student_number ignore nulls) over (
                partition by enrollment_academic_year, finalsite_student_id
                order by status_start_date asc
                rows between unbounded preceding and unbounded following
            ) as latest_powerschool_student_number,
        from transformations
    ),

    end_date_calc as (
        select
            * except (status_lag),

            lead(
                date_sub(status_start_date, interval 1 day),
                1,
                current_date('{{ var("local_timezone") }}')
            ) over (
                partition by finalsite_student_id, enrollment_year
                order by status_start_date asc
            ) as status_end_date,
        from dedupe
        where `status` != status_lag
    )

select
    *,

    enrollment_academic_year - 1 as sre_academic_year,

    cast(enrollment_academic_year as string)
    || '-'
    || right(
        cast(enrollment_academic_year + 1 as string), 2
    ) as enrollment_academic_year_display,

    if(
        status_end_date = status_start_date,
        1,
        date_diff(status_end_date, status_start_date, day)
    ) as days_in_status,

    date(enrollment_academic_year - 1, 10, 16) as sre_academic_year_start,
    date(enrollment_academic_year, 10, 15) as sre_academic_year_end,

    row_number() over (
        partition by enrollment_academic_year, finalsite_student_id
        order by status_start_date desc
    ) as rn,

from end_date_calc
