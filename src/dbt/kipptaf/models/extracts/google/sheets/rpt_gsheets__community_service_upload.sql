with
    cs_roster as (
        select
            co.student_number,
            co.academic_year,
            co.grade_level,
            co.school_abbreviation as school_name,
            b.behavior_date,
            b.behavior,
            b.notes,
            concat(b.staff_last_name, ', ', b.staff_first_name) as staff_name,
            cast(left(b.behavior, length(b.behavior) - 5) as int) as cs_hours
        from {{ ref("base_powerschool__student_enrollments") }} as co
        left join
            {{ ref("stg_deanslist__behavior") }} as b
            on (
                co.student_number = b.student_school_id
                and b.behavior_category = 'Community Service'
                and (b.behavior_date between co.entrydate and co.exitdate)
            )
        where
            co.grade_level between 9 and 12
            and co.is_enrolled_y1
            and co.academic_year >= {{ var("current_academic_year") }} - 1
    )

select
    academic_year,
    school_name,
    student_number as `StudentID`,
    _9 as `HOURS-9TH`,
    _10 as `HOURS-10TH`,
    _11 as `HOURS-11TH`,
    _12 as `HOURS-12TH`
from
    (
        select
            hs.academic_year,
            hs.school_name,
            hs.student_number,
            hs.grade_level,
            hs.cs_hours
        from cs_roster as hs
    )
    pivot (sum(cs_hours) for grade_level in (9, 10, 11, 12))
