with
    prev_year as (
        select
            student_number,

            academic_year + 1 as academic_year,

            max(is_enrolled_oct01) as is_enrolled_oct01_prev,
        from {{ ref("int_extracts__student_enrollments") }}
        group by student_number, academic_year
    )

select
    co.academic_year,
    co.student_number,
    co.student_name,
    co.region,
    co.school,
    co.grade_level,
    co.ethnicity,
    co.gender,
    co.year_in_network,
    co.exit_code_kf,
    co.exit_code_ts,
    co.is_retained_year,
    co.is_retained_ever,
    co.cohort,
    co.boy_status,
    co.is_self_contained,
    co.is_out_of_district,
    co.iep_status,
    co.ml_status,
    co.week_start_monday,
    co.week_end_sunday,
    co.week_number_academic_year,
    co.quarter,

    if(co.week_start_monday between co.entrydate and co.exitdate, 0, 1) as is_attrition,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
inner join
    prev_year as py
    on co.student_number = py.student_number
    and co.academic_year = py.academic_year
    and py.is_enrolled_oct01_prev
where
    co.academic_year >= {{ var("current_academic_year") - 2 }} and co.grade_level != 99
