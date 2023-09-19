select
    co.student_number,
    co.academic_year,

    rt.name as term,

    cum.cumulative_y1_gpa as gpa_cum,
    cum.cumulative_y1_gpa_projected as gpa_cum_projected,

    gpa.gpa_term as gpa_term,
    gpa.gpa_y1 as gpa_y1,

    null as promo_status_overall,
    null as promo_status_attendance,
    null as promo_status_lit,
    null as promo_status_grades,
    null as promo_status_qa_math,
    null as grades_y1_credits_projected,
    null as grades_y1_credits_enrolled,
    null as grades_y1_failing_projected,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on co.schoolid = rt.school_id
    and co.academic_year = rt.academic_year
    and rt.type = 'RT'
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
where co.academic_year = {{ var("current_academic_year") }} and co.rn_year = 1
