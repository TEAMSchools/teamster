select
    student_number,
    academic_year,
    week_start_monday,
    week_end_sunday,

    max(if(is_truant, 1, 0)) as is_truant_int,
from {{ ref("int_students__attendance_daily") }}
where academic_year >= {{ var("current_academic_year") - 1 }}
group by student_number, academic_year, week_start_monday, week_end_sunday
