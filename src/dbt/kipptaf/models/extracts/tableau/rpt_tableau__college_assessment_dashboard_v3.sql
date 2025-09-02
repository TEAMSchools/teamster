select
    e.academic_year,
    e.academic_year_display,
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.student_name,
    e.grade_level,
    e.enroll_status,
    e.cohort,
    e.is_504,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.salesforce_id as contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    r.administration_round,
    r.test_type,
    r.test_date,
    r.test_month,
    r.scope,
    r.subject_area,
    r.course_discipline,
    r.score_type,
    r.scale_score,
    r.rn_highest,
    r.max_scale_score,
    r.superscore,
    r.admin_season,
    r.grade_season,
    r.running_max_scale_score,
    r.running_superscore,

    p.psat89_count,
    p.psat10_count,
    p.psatnmsqt_count,
    p.sat_count,
    p.act_count,

    p.psat89_count_ytd,
    p.psat10_count_ytd,
    p.psatnmsqt_count_ytd,
    p.sat_count_ytd,
    p.act_count_ytd,

    if(e.iep_status = 'No IEP', 0, 1) as sped,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    {{ ref("int_students__college_assessment_roster") }} as r
    on e.academic_year = r.academic_year
    and e.student_number = r.student_number
    and {{ union_dataset_join_clause(left_alias="e", right_alias="r") }}
left join
    {{ ref("int_students__college_assessment_participation_roster") }} as p
    on e.student_number = p.student_number
    and e.grade_level = p.grade_level
    and {{ union_dataset_join_clause(left_alias="e", right_alias="p") }}
where e.rn_year = 1 and e.school_level = 'HS'
