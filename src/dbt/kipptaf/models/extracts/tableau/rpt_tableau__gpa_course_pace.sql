select
    p.studentid,
    p.schoolid,
    p.course_number,
    p.course_name,
    p._dbt_source_project,
    p.potential_credit_hours,
    p.target_cutoff_percent,
    p.y1_percent_current,
    p.term_percent_current,
    p.pace_percent,
    p.is_below_target,
    p.is_secured,
    p.is_locked,
    p.next_letter_grade,
    p.next_cutoff_percent,
    p.pace_percent_to_next,
    p.quickest_win_rank,

    co.academic_year,
    co.region,
    co.school,
    co.grade_level,
    co.student_number,
    co.student_name,
    co.advisory,
    co.school_leader_tableau_username,
from {{ ref("int_powerschool__course_pace") }} as p
inner join
    {{ ref("int_extracts__student_enrollments") }} as co
    on p.studentid = co.studentid
    and p.schoolid = co.schoolid
    and p._dbt_source_project = co._dbt_source_project
    and co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
