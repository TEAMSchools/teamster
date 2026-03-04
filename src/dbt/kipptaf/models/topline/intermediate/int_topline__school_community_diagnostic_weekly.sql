select
    co.student_number,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,

    sc.average_rating,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
inner join
    {{ ref("int_topline__school_community_diagnostic") }} as sc
    on co.student_number = sc.student_number
    and co.academic_year = sc.academic_year
    and co.schoolid = sc.schoolid
where co.academic_year >= {{ var("current_academic_year") - 1 }}
