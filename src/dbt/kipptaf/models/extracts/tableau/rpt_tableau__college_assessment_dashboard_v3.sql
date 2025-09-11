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
    e.grad_iep_exempt_status_overall,
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
    r.previous_total_score_change,
    r.rn_highest,
    r.max_scale_score,
    r.superscore,
    r.running_max_scale_score,
    r.running_superscore,
    r.hs_ready_score,
    r.hs_ready_goal,
    r.college_ready_score,
    r.college_ready_goal,
    r.per_16_plus_score,
    r.per_880_plus_score,
    r.per_17_plus_score,
    r.per_890_plus_score,
    r.per_21_plus_score,
    r.per_1010_plus_score,
    r.per_16_plus_goal,
    r.per_880_plus_goal,
    r.per_17_plus_goal,
    r.per_890_plus_goal,
    r.per_21_plus_goal,
    r.per_1010_plus_goal,

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
    p.act_group_0_score,
    p.act_group_0_goal,
    p.act_group_1_score,
    p.act_group_1_goal,
    p.act_group_2_plus_score,
    p.act_group_2_plus_goal,
    p.sat_group_0_score,
    p.sat_group_0_goal,
    p.sat_group_1_score,
    p.sat_group_1_goal,
    p.sat_group_2_plus_score,
    p.sat_group_2_plus_goal,
    p.psat89_group_0_score,
    p.psat89_group_0_goal,
    p.psat89_group_1_score,
    p.psat89_group_1_goal,
    p.psat89_group_2_plus_score,
    p.psat89_group_2_plus_goal,
    p.psat10_group_0_score,
    p.psat10_group_0_goal,
    p.psat10_group_1_score,
    p.psat10_group_1_goal,
    p.psat10_group_2_plus_score,
    p.psat10_group_2_plus_goal,
    p.psatnmsqt_group_0_score,
    p.psatnmsqt_group_0_goal,
    p.psatnmsqt_group_1_score,
    p.psatnmsqt_group_1_goal,
    p.psatnmsqt_group_2_plus_score,
    p.psatnmsqt_group_2_plus_goal,

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
    and r.test_month is not null
    and r.score_type not in (
        'psat10_reading',
        'psat10_math_test',
        'sat_math_test_score',
        'sat_reading_test_score'
    )
left join
    {{ ref("int_students__college_assessment_participation_roster") }} as p
    on e.student_number = p.student_number
    and e.grade_level = p.grade_level
    and {{ union_dataset_join_clause(left_alias="e", right_alias="p") }}
where e.rn_year = 1 and e.school_level = 'HS'
