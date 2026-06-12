-- at most one is_current_record = TRUE per (enrollment, academic year)
-- academic_year is no longer stored on the fact; derive the KIPP July-start
-- year from date_key (equals the term_academic_year that anchors
-- is_current_record on every row)
select
    student_enrollment_key,
    if(
        extract(month from date_key) >= 7,
        extract(year from date_key),
        extract(year from date_key) - 1
    ) as academic_year,
    countif(is_current_record) as n_current,
from {{ ref("fct_student_enrollment_daily") }}
group by
    student_enrollment_key,
    if(
        extract(month from date_key) >= 7,
        extract(year from date_key),
        extract(year from date_key) - 1
    )
having countif(is_current_record) > 1
