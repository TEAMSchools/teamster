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
    case
        when
            co.academic_year = {{ var("current_academic_year") }}
            and current_date('America/New_York')
            between cw.week_start_monday and cw.week_end_sunday
        then true
        when
            cw.week_start_monday = max(cw.week_start_monday) over (
                partition by co.academic_year, co.schoolid
            )
        then true
        else false
    end as is_current_week,
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__calendar_week") }} as cw
    on co.academic_year = cw.academic_year
    and co.schoolid = cw.schoolid
