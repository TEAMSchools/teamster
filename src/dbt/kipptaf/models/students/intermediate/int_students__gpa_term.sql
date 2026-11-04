-- PowerSchool only: Focus's student_gpa_calculated has no term-grained row.
-- A Focus branch joins here when Focus produces a term GPA.
select
    _dbt_source_relation,
    _dbt_source_project,
    studentid,
    schoolid,
    yearid,
    academic_year,
    term_name,
    semester,
    gpa_term,
    gpa_y1,
    gpa_y1_unweighted,
    gpa_semester,
    n_failing_y1,
    total_credit_hours_term,
    total_credit_hours_y1,
    grade_avg_term,
    grade_avg_y1,
    students_student_number as student_number,
from {{ ref("int_powerschool__gpa") }}
