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

    w.week_start_monday,
    w.week_end_sunday,
    w.week_number_academic_year,
    w.quarter,

    if(co.lep_status, 'ML', 'Not ML') as ml_status,
    if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

    if(w.week_start_monday between co.entrydate and co.exitdate, 0, 1) as is_attrition,
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    prev_year as py
    on co.student_number = py.student_number
    and co.academic_year = py.academic_year
    and py.is_enrolled_oct01_prev
left join
    {{ ref("int_powerschool__calendar_week") }} as w
    on co.academic_year = w.academic_year
    and co.schoolid = w.schoolid
where
    co.academic_year >= {{ var("current_academic_year") - 2 }} and co.grade_level != 99
