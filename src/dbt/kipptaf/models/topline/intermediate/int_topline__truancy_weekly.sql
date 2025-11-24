select
    student_number,
    schoolid,
    academic_year,
    week_start_monday,
    week_end_sunday,
    week_number_academic_year,

    max(if(is_truant, 1, 0)) as is_truant_int,
from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
group by
    student_number,
    schoolid,
    academic_year,
    week_start_monday,
    week_end_sunday,
    week_number_academic_year
