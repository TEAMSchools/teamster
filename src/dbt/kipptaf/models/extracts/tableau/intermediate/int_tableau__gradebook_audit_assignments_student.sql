select
    ce._dbt_source_relation,
    ce.academic_year,
    ce.academic_year_display,
    ce.yearid,
    ce.region,
    ce.school_level,
    ce.schoolid,
    ce.school,
    ce.students_dcid,
    ce.studentid,
    ce.student_number,
    ce.student_name,
    ce.grade_level,
    ce.salesforce_id,
    ce.ktc_cohort,
    ce.enroll_status,
    ce.cohort,
    ce.gender,
    ce.ethnicity,
    ce.advisory,
    ce.hos,
    ce.year_in_school,
    ce.year_in_network,
    ce.rn_undergrad,
    ce.is_out_of_district,
    ce.is_self_contained,
    ce.is_retained_year,
    ce.is_retained_ever,
    ce.lunch_status,
    ce.gifted_and_talented,
    ce.iep_status,
    ce.lep_status,
    ce.is_504,
    ce.is_counseling_services,
    ce.is_student_athlete,
    ce.`ada`,
    ce.ada_above_or_at_80,

    ce.sectionid,
    ce.course_number,
    ce.date_enrolled,
    ce.sections_dcid,
    ce.section_number,
    ce.external_expression,
    ce.termid,
    ce.credit_type,
    ce.course_name,
    ce.exclude_from_gpa,
    ce.teacher_number,
    ce.teacher_name,
    ce.is_ap_course,

    ce.teacher_tableau_username,
    ce.manager_employee_number,
    ce.manager_name,
    ce.manager_tableau_username,
    ce.school_leader,
    ce.school_leader_tableau_username,
    ce.region_school_level,
    ce.quarter,
    ce.semester,
    ce.quarter_start_date,
    ce.quarter_end_date,
    ce.is_current_term,
    ce.section_or_period,
    ce.assignment_category_name,
    ce.assignment_category_code,
    ce.assignment_category_term,
    ce.expectation,
    ce.notes,

    ce.quarter_course_percent_grade,
    ce.quarter_course_grade_points,
    ce.quarter_comment_value,
    ce.category_quarter_percent_grade,

    a.assignmentid,
    a.assignment_name,
    a.duedate,
    a.scoretype,
    a.scorepoints,
    a.totalpointvalue,
    a.is_exempt,
    a.is_expected_late,
    a.is_expected_missing,
    a.is_expected_zero,
    a.is_expected_academic_dishonesty,
    a.is_expected_null,
    a.score_entered,
    a.assign_final_score_percent,
    a.half_total_point_value,

    a.is_expected as assign_expected_to_be_scored,
    a.is_expected_scored as assign_expected_with_score,

    if(a.is_expected_null = 1, true, false) as assign_null_score,

    if(a.score_entered > a.totalpointvalue, true, false) as assign_score_above_max,

    if(
        ce.assignment_category_code = 'W'
        and a.is_expected_missing = 0
        and a.score_entered < 5,
        true,
        false
    ) as assign_w_score_less_5,

    if(
        ce.assignment_category_code = 'H'
        and a.is_expected_missing = 0
        and a.score_entered < 5,
        true,
        false
    ) as assign_h_score_less_5,

    if(
        ce.assignment_category_code = 'F'
        and a.is_expected_missing = 0
        and a.score_entered < 5,
        true,
        false
    ) as assign_f_score_less_5,

    if(
        ce.assignment_category_code = 'W'
        and ce.school_level != 'HS'
        and a.is_expected_missing = 1
        and a.score_entered != 5,
        true,
        false
    ) as assign_w_missing_score_not_5,

    if(
        ce.assignment_category_code = 'H'
        and ce.school_level != 'HS'
        and a.is_expected_missing = 1
        and a.score_entered != 5,
        true,
        false
    ) as assign_h_missing_score_not_5,

    if(
        ce.assignment_category_code = 'F'
        and ce.school_level != 'HS'
        and a.is_expected_missing = 1
        and a.score_entered != 5,
        true,
        false
    ) as assign_f_missing_score_not_5,

    if(
        ce.assignment_category_code = 'W'
        and ce.school_level = 'HS'
        and a.is_expected_missing = 1
        and a.score_entered != 0,
        true,
        false
    ) as assign_w_missing_score_not_0,

    if(
        ce.assignment_category_code = 'H'
        and ce.school_level = 'HS'
        and a.is_expected_missing = 1
        and a.score_entered != 0,
        true,
        false
    ) as assign_h_missing_score_not_0,

    if(
        ce.assignment_category_code = 'F'
        and ce.school_level = 'HS'
        and a.is_expected_missing = 1
        and a.score_entered != 0,
        true,
        false
    ) as assign_f_missing_score_not_0,

    if(
        ce.assignment_category_code = 'S'
        and ce.school_level = 'HS'
        and a.is_expected_missing = 1
        and a.score_entered != 0,
        true,
        false
    ) as assign_s_missing_score_not_0,

    if(
        ce.assignment_category_code = 'S'
        and ce.school_level != 'HS'
        and a.score_entered < a.half_total_point_value,
        true,
        false
    ) as assign_s_score_less_50p,

    if(
        ce.assignment_category_code = 'S'
        and ce.school_level = 'HS'
        and a.is_missing = 0
        and a.score_entered < a.half_total_point_value,
        true,
        false
    ) as assign_s_hs_score_less_50p,

from {{ ref("int_tableau__gradebook_audit_student_scaffold") }} as ce
left join
    {{ ref("int_powerschool__gradebook_assignments_scores") }} as a
    on ce.sections_dcid = a.sectionsdcid
    and ce.students_dcid = a.students_dcid
    and ce.assignment_category_code = a.category_code
    and a.duedate between ce.quarter_start_date and ce.quarter_end_date
    and ce.date_enrolled <= a.duedate
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="a") }}
    and a.iscountedinfinalgrade = 1
    and a.scoretype in ('POINTS', 'PERCENT')
where ce.scaffold_name = 'student_category_scaffold'
