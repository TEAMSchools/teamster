select
    ce._dbt_source_relation,
    ce.academic_year,
    ce.region,
    ce.school_level,
    ce.schoolid,
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
    ce.year_in_school,
    ce.year_in_network,
    ce.rn_undergrad,
    ce.is_out_of_district,
    ce.is_retained_year,
    ce.is_retained_ever,
    ce.lunch_status,
    ce.gifted_and_talented,
    ce.iep_status,
    ce.lep_status,
    ce.is_504,
    ce.is_counseling_services,
    ce.is_student_athlete,
    ce.ada,
    ce.ada_above_or_at_80,
    ce.sectionid,
    ce.course_number,
    ce.date_enrolled,
    ce.sections_dcid,
    ce.credit_type,
    ce.teacher_number,
    ce.is_ap_course,
    ce.assignment_category_code,
    ce.assignment_category_term,
    ce.quarter,
    ce.is_quarter_end_date_range,
    ce.week_start_date,
    ce.week_end_date,
    ce.week_number_quarter,
    ce.quarter_course_percent_grade,
    ce.quarter_course_grade_points,
    ce.quarter_conduct,
    ce.quarter_comment_value,
    ce.category_quarter_percent_grade,
    ce.category_quarter_average_all_courses,

    a.assignmentid,
    a.scorepoints,
    a.is_exempt,
    a.is_expected_late,
    a.is_expected_missing,
    a.is_expected_academic_dishonesty,
    a.is_expected_null,
    a.score_entered,
    a.assign_final_score_percent,

    -- exempt, nulls and max
    if(a.is_expected_null = 1, true, false) as assign_null_score,

    if(a.score_entered > a.totalpointvalue, true, false) as assign_score_above_max,

    -- less than 5 score checks
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

    -- miss assign not score 5 for non-hs
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

    -- miss assign not score 0 for hs
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

    -- 50% s assign min
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

    -- conversion chart
    if(
        a.is_exempt = 0
        and ce.school_level = 'MS'
        and ce.assignment_category_code = 'S'
        and a.is_expected_null = 0
        and a.assign_final_score_percent
        not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
        true,
        false
    ) as assign_s_ms_score_not_conversion_chart_options,

    if(
        a.is_exempt = 0
        and ce.school_level = 'HS'
        and ce.assignment_category_code = 'S'
        and not ce.is_ap_course
        and a.is_expected_null = 0
        and a.assign_final_score_percent
        not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100),
        true,
        false
    ) as assign_s_hs_score_not_conversion_chart_options,

from
    {{ ref("int_tableau__gradebook_audit_section_week_category_student_scaffold") }}
    as ce
left join
    {{ ref("int_powerschool__gradebook_assignments_scores") }} as a
    on ce.sections_dcid = a.sectionsdcid
    and ce.students_dcid = a.students_dcid
    and ce.assignment_category_code = a.category_code
    and a.duedate between ce.week_start_date and ce.week_end_date
    and ce.date_enrolled <= a.duedate
    and {{ union_dataset_join_clause(left_alias="ce", right_alias="a") }}
    and a.iscountedinfinalgrade = 1
    and a.scoretype in ('POINTS', 'PERCENT')
