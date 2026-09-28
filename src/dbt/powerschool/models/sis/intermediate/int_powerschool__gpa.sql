select
    gt.studentid,
    gt.schoolid,
    gt.yearid,
    gt.academic_year,
    gt.term_name,
    gt.semester,
    gt.gpa_term,
    gt.gpa_y1,
    gt.gpa_y1_unweighted,
    gt.gpa_semester,
    gt.n_failing_y1,
    gt.total_credit_hours_term,
    gt.total_credit_hours_y1,
    gt.grade_avg_term,
    gt.grade_avg_y1,
    gt.students_student_number,

    gc.cumulative_y1_gpa,
    gc.cumulative_y1_gpa_unweighted,
    gc.cumulative_y1_gpa_projected,
    gc.earned_credits_cum,
    gc.potential_credits_cum,
from {{ ref("int_powerschool__gpa_term") }} as gt
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on gt.studentid = gc.studentid
    and gt.schoolid = gc.schoolid
