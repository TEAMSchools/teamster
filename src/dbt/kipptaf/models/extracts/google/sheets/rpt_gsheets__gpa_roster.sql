select
    academic_year_display as academic_year,
    region,
    student_name,
    student_number,
    school,
    grade_level,
    team,
    iep_status,
    gender,
    lep_status,
    gifted_and_talented,
    is_504,

    gpa_term_q1,
    gpa_term_q2,
    gpa_term_q3,
    gpa_term_q4,

    gpa_y1_q1,
    gpa_y1_q2,
    gpa_y1_q3,
    gpa_y1_q4,
from
    (
        select
            co.academic_year_display,
            co.region,
            co.school,
            co.grade_level,
            co.team,
            co.student_number,
            co.student_name,
            co.iep_status,
            co.gender,
            co.lep_status,
            co.is_504,
            term,
            gpa.gpa_term,
            gpa.gpa_y1,

            coalesce(co.gifted_and_talented, 'N') as gifted_and_talented,
        from {{ ref("int_tableau__student_enrollments") }} as co
        cross join unnest(['Q1', 'Q2', 'Q3', 'Q4']) as term
        left join
            {{ ref("int_powerschool__gpa_term") }} as gpa
            on co.studentid = gpa.studentid
            and co.yearid = gpa.yearid
            and term = gpa.term_name
            and co.schoolid = gpa.schoolid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.enroll_status = 0
            and co.grade_level >= 5
    ) pivot (
        max(gpa_term) as gpa_term,
        max(gpa_y1) as gpa_y1 for term in ('Q1', 'Q2', 'Q3', 'Q4')
    )