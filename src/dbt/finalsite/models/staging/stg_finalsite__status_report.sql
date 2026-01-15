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

            cast(left(enrollment_year, 4) as int) as academic_year,

            date(
                cast(`timestamp` as timestamp), '{{ var("local_timezone") }}'
            ) as status_start_date,

            initcap(replace(`status`, '_', ' ')) as detailed_status,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

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
                date_sub(status_start_date, interval 1 day),
                1,
                current_date('{{ var("local_timezone") }}')
            ) over (
                partition by finalsite_student_id, enrollment_year
                order by status_start_date asc
            ) as status_end_date,

        from transformations
    )

select
    *,

    if(
        status_end_date = status_start_date,
        1,
        date_diff(status_end_date, status_start_date, day)
    ) as days_in_status,

    date(academic_year, 10, 16) as sre_year_start,
    date(academic_year + 1, 10, 15) as sre_year_end,

from end_date_calc
