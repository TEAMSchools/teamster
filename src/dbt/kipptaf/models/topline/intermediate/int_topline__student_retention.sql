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
            enrollment_day,
            1 as is_enrolled_day_int,
            if
            (
                extract(month from enrollment_day) >= 7,
                extract(year from enrollment_day),
                extract(year from enrollment_day) - 1
            ) as academic_year,
            if
            (
                extract(month from enrollment_day) < 10,
                extract(year from enrollment_day) - 1,
                extract(year from enrollment_day)
            ) as attrition_year,
        from
            {{ ref("int_extracts__student_enrollments") }} as co,
            unnest(
                generate_date_array(entrydate, exitdate, interval 1 day)
            ) as enrollment_day
    ),

    is_enrolled as (
        select
            student_number,
            attrition_year,
            max(
                if(ed.enrollment_day = date(ed.attrition_year, 10, 1), true, false)
            ) over (partition by ed.student_number, ed.attrition_year)
            as is_enrolled_oct01,
        from enrolled_days as ed
    ),

    attrition_years_distinct as (
        select ed.student_number, ed.attrition_year,
        from enrolled_days as ed
        inner join
            is_enrolled as ie
            on ed.student_number = ie.student_number
            and ed.attrition_year = ie.attrition_year
            and ie.is_enrolled_oct01
        group by ed.student_number, ed.attrition_year
    ),

    attrition_calendar as (
        select
            attrition_day,
            if
            (
                extract(month from attrition_day) < 10,
                extract(year from attrition_day) - 1,
                extract(year from attrition_day)
            ) as attrition_year,
        from
            unnest(
                generate_date_array(
                    '2022-10-01', current_date('America/New_York'), interval 1 day
                )
            ) as attrition_day
    ),

    attrition_scaffold as (
        select ayd.student_number, ayd.attrition_year, ac.attrition_day,
        from attrition_years_distinct as ayd
        inner join attrition_calendar as ac on ayd.attrition_year = ac.attrition_year
    ),

    final as (
        select
            s.student_number,
            s.attrition_year,
            s.attrition_day,

            coalesce(ed.is_enrolled_day_int, 0) as is_enrolled_day_int,
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
            and s.attrition_year = ed.attrition_year
            and s.attrition_day = ed.enrollment_day
    )

select region, avg(is_enrolled_day_int)
from final
where attrition_year = 2024 and attrition_day = '2025-08-22'
group by all
