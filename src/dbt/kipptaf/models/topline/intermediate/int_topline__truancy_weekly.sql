select
    co.student_number,
    co.schoolid,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,
    co.week_number_academic_year,

    max(if(t.is_truant, 1, 0)) as is_truant_int,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
inner join
    {{ ref("int_students__truancy") }} as t
    on co.student_number = t.student_number
    and co.academic_year = t.academic_year
    and t.date_day between co.week_start_monday and co.week_end_sunday
where co.is_enrolled_week
group by
    co.student_number,
    co.schoolid,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,
    co.week_number_academic_year
