select
    e.academic_year,
    e.academic_year_display,
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.enroll_status,
    e.cohort,
    e.iep_status,
    e.is_504,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.student_email,
    e.rn_undergrad,
    e.salesforce_id,
    e.ktc_cohort,
    e.year_in_network,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    gc.cumulative_y1_gpa,
    gc.cumulative_y1_gpa_unweighted,
    gc.cumulative_y1_gpa_projected,
    gc.cumulative_y1_gpa_projected_s1,
    gc.cumulative_y1_gpa_projected_s1_unweighted,
    gc.core_cumulative_y1_gpa,

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

    g1.aligned_goal_category,
    g1.goal_category,
    g1.goal_type,
    g1.goal_subtype,
    g1.score,
    g1.goal,

    g2.aligned_goal_category as board_aligned_goal_category,
    g2.goal_category as board_goal_category,
    g2.goal_type as board_goal_type,
    g2.goal_subtype as board_goal_subtype,
    g2.score as board_score,
    g2.goal as board_goal,

    concat(
        's', '_', r.grade_season, ' ', r.scope, ' ', r.subject_area, ' ', r.test_type
    ) as test_season_for_roster,

    concat(
        r.administration_round, ' ', r.scope, ' ', r.subject_area, ' ', r.test_type
    ) as test_admin_for_roster,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gc
    on e.studentid = gc.studentid
    and e.schoolid = gc.schoolid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="gc") }}
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
left join
    {{ ref("stg_google_sheets__kippfwd_goals") }} as g1
    on r.academic_year = g1.academic_year
    and r.scope = g1.expected_scope
    and r.subject_area = g1.expected_subject_area
    and g1.goal_type in ('Attempts', 'Benchmark')
left join
    {{ ref("stg_google_sheets__kippfwd_goals") }} as g2
    on r.academic_year = g2.academic_year
    and r.grade_level = g2.grade_level
    and r.scope = g2.expected_scope
    and r.subject_area = g2.expected_subject_area
    and g1.goal_type = 'Board'
where
    e.rn_year = 1
    and e.school_level = 'HS'
    and r.test_month is not null
    and r.score_type not in (
        'psat10_reading',
        'psat10_math_test',
        'sat_math_test_score',
        'sat_reading_test_score'
    )
