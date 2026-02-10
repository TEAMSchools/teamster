with
    transformations as (
        select
            * except (
                powerschool_student_number,
                `timestamp`,
                grade_level,
                enrollment_type,
                source_file_name
            ),

            enrollment_type as enrollment_type_raw,
            grade_level as grade_level_name,

            cast(powerschool_student_number as int) as powerschool_student_number,
            cast(`timestamp` as timestamp) as status_start_timestamp,

            cast(left(enrollment_year, 4) as int) as enrollment_academic_year,

            regexp_extract(
                source_file_name, r'\w+((?:Current|Next)_Year).+'
            ) as extract_year,

            parse_datetime(
                '%d-%m-%Y_%H-%M-%S',
                regexp_extract(source_file_name, r'\w+_(\d+-\d+-\d+_\d+-\d+-\d+).+')
            ) as extract_timestamp,

            initcap(replace(`status`, '_', ' ')) as detailed_status,

            if(
                grade_level in ('K', 'Kindergarten'),
                0,
                cast(regexp_extract(grade_level, r'\d+') as int)
            ) as grade_level,

            case
                `status`
                when 'inquiry'
                then 1
                when 'inquiry_completed'
                then 2
                when 'inactive_inquiry'
                then 3
                when 'applicant'
                then 4
                when 'application_withdrawn'
                then 5
                when 'deferred'
                then 6
                when 'application_complete'
                then 7
                when 'review_in_progress'
                then 8
                when 'waitlisted'
                then 9
                when 'denied'
                then 10
                when 'accepted'
                then 11
                when 'assigned_school'
                then 12
                when 'did_not_enroll'
                then 13
                when 'campus_transfer_requested'
                then 14
                when 'parent_declined'
                then 15
                when 'enrollment_in_progress'
                then 16
                when 'academic_hold'
                then 17
                when 'financial_hold'
                then 18
                when 'not_enrolling'
                then 19
                when 'enrolled'
                then 20
                when 'mid_year_withdrawal'
                then 21
                when 'never_attended'
                then 22
                when 'retained'
                then 23
                when 'summer_withdraw'
                then 24
            end as status_order,
        from {{ source("finalsite", "status_report") }}
    ),

    dedupe as (
        select
            *,

            date(
                status_start_timestamp, '{{ var("local_timezone") }}'
            ) as status_start_date,

            lag(`status`, 1, '') over (
                partition by finalsite_student_id, enrollment_year
                order by status_start_timestamp asc, status_order asc
            ) as status_lag,

            last_value(school ignore nulls) over (
                partition by enrollment_academic_year, finalsite_student_id
                order by status_start_timestamp asc, status_order asc
                rows between unbounded preceding and unbounded following
            ) as latest_school,

            last_value(powerschool_student_number ignore nulls) over (
                partition by enrollment_academic_year, finalsite_student_id
                order by status_start_timestamp asc, status_order asc
                rows between unbounded preceding and unbounded following
            ) as latest_powerschool_student_number,
        from transformations
    ),

    end_date_calc as (
        select
            * except (status_lag),

            lead(status_start_timestamp, 1, '9999-12-31') over (
                partition by finalsite_student_id, enrollment_year
                order by status_start_timestamp asc, status_order asc
            ) as status_end_timestamp,

            lead(
                status_start_date,
                1,
                current_date('{{ var("local_timezone") }}')
            ) over (
                partition by finalsite_student_id, enrollment_year
                order by status_start_date asc, status_order asc
            ) as status_end_date,
        from dedupe
        where `status` != status_lag
    )

select
    *,

    enrollment_academic_year - 1 as sre_academic_year,

    date(enrollment_academic_year - 1, 10, 16) as sre_academic_year_start,
    date(enrollment_academic_year, 6, 30) as sre_academic_year_end,

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

    row_number() over (
        partition by enrollment_academic_year, finalsite_student_id
        order by status_start_timestamp desc, status_order desc
    ) as rn,

from end_date_calc
