select
    co.student_number,
    co.academic_year,

    rt.name as term,

    cum.cumulative_y1_gpa as gpa_cum,
    cum.cumulative_y1_gpa_projected as gpa_cum_projected,

    gpa.gpa_term,
    gpa.gpa_y1,

    p.overall_status as promo_status_overall,
    p.attendance_status as promo_status_attendance,
    p.academic_status as promo_status_grades,
    cum.earned_credits_cum as grades_y1_credits_projected,
    p.n_failing as grades_y1_failing_projected,
    p.ada_term_running,
    p.projected_credits_y1_term,

    null as promo_status_lit,
    null as promo_status_qa_math,
    null as grades_y1_credits_enrolled,

    case
        co.grade_level when 9 then 25 when 10 then 50 when 11 then 85 when 12 then 120
    end as promo_credits_needed,

    coalesce(p.iready_reading_recent, '(No Data)') as iready_reading_recent,
    coalesce(p.iready_math_recent, '(No Data)') as iready_math_recent,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join (select *, from unnest(['Q1', 'Q2', 'Q3', 'Q4']) as `name`) as rt
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as cum
    on co.studentid = cum.studentid
    and co.schoolid = cum.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="cum") }}
left join
    {{ ref("int_powerschool__gpa_term") }} as gpa
    on co.studentid = gpa.studentid
    and co.yearid = gpa.yearid
    and rt.name = gpa.term_name
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
left join
    {{ ref("int_reporting__promotional_status") }} as p
    on co.student_number = p.student_number
    and co.academic_year = p.academic_year
    and rt.name = p.term_name
where co.academic_year = {{ var("current_academic_year") }} and co.rn_year = 1
