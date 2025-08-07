select
    co.*,

    cw.week_start_monday,
    cw.week_end_sunday,
    cw.quarter,
    cw.semester,
    cw.school_week_start_date,
    cw.school_week_end_date,
    cw.week_number_academic_year,
    cw.week_number_quarter,

    if(
        cw.week_start_monday between co.entrydate and co.exitdate, true, false
    ) as is_enrolled_week,
from {{ ref("int_extracts__student_enrollments_subjects") }} as co
inner join
    {{ ref("int_powerschool__calendar_week") }} as cw
    on co.academic_year = cw.academic_year
    and co.schoolid = cw.schoolid
where co.grade_level != 99
