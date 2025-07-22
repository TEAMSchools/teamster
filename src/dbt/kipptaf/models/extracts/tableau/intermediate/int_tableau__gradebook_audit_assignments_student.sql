select
    ce.*,

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
    a.is_expected_null,
    a.score_entered,
    a.assign_final_score_percent,

    a.is_expected as assign_expected_to_be_scored,
    a.is_expected_scored as assign_expected_with_score,

    -- exempt, nulls and max
    if(a.is_exempt = 1 and a.is_null = 0, true, false) as assign_exempt_with_score,

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

    -- 50% s assign min
    if(
        ce.assignment_category_code = 'S'
        and a.score_entered < a.half_total_point_value,
        true,
        false
    ) as assign_s_score_less_50p,

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
    {{ ref("int_tableau__gradebook_audit_section_week_student_category_scaffold") }}
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
left join
    {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
    on ce.academic_year = e.academic_year
    and ce.region = e.region
    and ce.school_level = e.school_level
    and ce.course_number = e.course_number
    and e.view_name = 'int_tableau__gradebook_audit_assignments_student'
    and e.course_number is not null
where e.`include` is null
