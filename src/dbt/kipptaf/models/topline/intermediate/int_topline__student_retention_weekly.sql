with
    enrolled_days as (
        select
            co.student_number,
            co.student_name,
            co.region,
            co.school,
            co.schoolid,
            co.entrydate,
            co.exitdate,
            co.exitcode,
            co.enroll_status,
            co.next_year_schoolid,

            enrollment_day,

            1 as is_enrolled_day_int,

            if(
                extract(month from enrollment_day) >= 7,
                extract(year from enrollment_day),
                extract(year from enrollment_day) - 1
            ) as academic_year,

            if(
                extract(month from enrollment_day) < 10,
                extract(year from enrollment_day) - 1,
                extract(year from enrollment_day)
            ) as attrition_year,
        from {{ ref("int_extracts__student_enrollments") }} as co
        cross join
            unnest(
                generate_date_array(co.entrydate, co.exitdate, interval 1 day)
            ) as enrollment_day
    ),

    is_enrolled as (
        select
            student_number,
            attrition_year,

            max(if(enrollment_day = date(attrition_year, 10, 1), true, false)) over (
                partition by student_number, attrition_year
            ) as is_enrolled_oct01,
        from enrolled_days
    ),

    attrition_years_distinct as (
        select distinct ed.student_number, ed.attrition_year,
        from enrolled_days as ed
        inner join
            is_enrolled as ie
            on ed.student_number = ie.student_number
            and ed.attrition_year = ie.attrition_year
            and ie.is_enrolled_oct01
    ),

    attrition_calendar as (
        select
            attrition_day,

            if(
                extract(month from attrition_day) < 10,
                extract(year from attrition_day) - 1,
                extract(year from attrition_day)
            ) as attrition_year,
        from
            unnest(
                generate_date_array(

                    date({{ var("current_academic_year") - 3 }}, 10, 1),
                    current_date('America/New_York'),
                    interval 1 day
                )
            ) as attrition_day
    ),

    attrition_scaffold as (
        select ayd.student_number, ayd.attrition_year, ac.attrition_day,
        from attrition_years_distinct as ayd
        inner join attrition_calendar as ac on ayd.attrition_year = ac.attrition_year
    ),

    scaffold_full as (
        select
            s.student_number,
            s.attrition_year,
            s.attrition_day,

            ed.is_enrolled_day_int,

            last_value(ed.academic_year ignore nulls) over (
                partition by s.student_number order by s.attrition_day
            ) as academic_year,

            last_value(ed.next_year_schoolid ignore nulls) over (
                partition by s.student_number order by s.attrition_day
            ) as next_year_schoolid,

            last_value(ed.student_name ignore nulls) over (
                partition by s.student_number order by s.attrition_day
            ) as student_name,

            last_value(ed.region ignore nulls) over (
                partition by s.student_number order by s.attrition_day
            ) as region,

            last_value(ed.school ignore nulls) over (
                partition by s.student_number order by s.attrition_day
            ) as school,

            last_value(ed.schoolid ignore nulls) over (
                partition by s.student_number order by s.attrition_day
            ) as schoolid,

            last_value(ed.entrydate ignore nulls) over (
                partition by s.student_number order by s.attrition_day
            ) as entrydate,

            last_value(ed.exitdate ignore nulls) over (
                partition by s.student_number order by s.attrition_day
            ) as exitdate,
        from attrition_scaffold as s
        left join
            enrolled_days as ed
            on s.student_number = ed.student_number
            and s.attrition_day = ed.enrollment_day
    ),

    retention_daily as (
        select
            student_number,
            attrition_year,
            academic_year,
            attrition_day,
            next_year_schoolid,
            student_name,
            region,
            school,
            schoolid,
            entrydate,
            exitdate,

            date_trunc(attrition_day, week(monday)) as week_start_monday,
            date_add(
                date_trunc(attrition_day, week(monday)), interval 6 day
            ) as week_end_sunday,

            case
                when attrition_day > exitdate and next_year_schoolid = 999999
                then 1
                when is_enrolled_day_int = 1
                then 1
                else 0
            end as is_enrolled_day_int,
        from scaffold_full
    )

select
    student_number,
    attrition_year,
    academic_year,
    next_year_schoolid,
    student_name,
    region,
    school,
    schoolid,
    entrydate,
    exitdate,
    week_start_monday,
    week_end_sunday,

    max(is_enrolled_day_int) as is_retained_int,
    max(1 - is_enrolled_day_int) as is_attrition_int,
from retention_daily as rd
group by
    student_number,
    attrition_year,
    academic_year,
    next_year_schoolid,
    student_name,
    region,
    school,
    schoolid,
    entrydate,
    exitdate,
    week_start_monday,
    week_end_sunday
