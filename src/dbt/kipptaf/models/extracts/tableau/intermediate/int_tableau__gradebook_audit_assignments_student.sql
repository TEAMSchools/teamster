with
    roster_assignments_scores as (
        select
            ce.*,

            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,
            a.category_name,

            s.scorepoints,
            s.actualscoreentered,

            coalesce(s.islate, 0) as is_late,
            coalesce(s.isexempt, 0) as is_exempt,
            coalesce(s.ismissing, 0) as is_missing,

            if(s.scorepoints = 0, 1, 0) as is_zero,

            if(
                a.scoretype = 'POINTS',
                s.scorepoints,
                safe_cast(s.actualscoreentered as numeric)
            ) as score_entered,

            if(
                a.scoretype = 'POINTS',
                round(safe_divide(s.scorepoints, a.totalpointvalue) * 100, 2),
                safe_cast(s.actualscoreentered as numeric)
            ) as assign_final_score_percent,

        from
            {{
                ref(
                    "int_tableau__gradebook_audit_section_week_student_category_scaffold"
                )
            }}
            as ce
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on ce.sections_dcid = a.sectionsdcid
            and ce.assignment_category_code = a.category_code
            and a.duedate between ce.week_start_date and ce.week_end_date
            and ce.date_enrolled <= a.duedate
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="a") }}
            and a.iscountedinfinalgrade = 1
            and a.scoretype in ('POINTS', 'PERCENT')
        left join
            {{ ref("stg_powerschool__assignmentscore") }} as s
            on ce.students_dcid = s.studentsdcid
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="s") }}
            and a.assignmentsectionid = s.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on ce.academic_year = e.academic_year
            and ce.region = e.region
            and ce.school_level = e.school_level
            and ce.course_number = e.course_number
            and e.view_name = 'int_tableau__gradebook_audit_assignments_student'
            and e.course_number is not null
        where e.`include` is null
    )

select
    *,

    -- scoring checks
    if(
        assignmentid is not null and is_exempt = 0, true, false
    ) as assign_expected_to_be_scored,

    if(
        assignmentid is not null and scorepoints is not null and is_exempt = 0,
        true,
        false
    ) as assign_scored,

    if(
        assignmentid is not null
        and is_exempt = 0
        and ((is_missing = 0 and scorepoints is not null) or scorepoints is not null),
        true,
        false
    ) as assign_expected_with_score,

    -- exempt, nulls and max
    if(is_exempt = 1 and scorepoints > 0, true, false) as assign_exempt_with_score,

    if(
        assignmentid is not null and scorepoints is null and is_exempt = 0, true, false
    ) as assign_null_score,

    if(scorepoints > totalpointvalue, true, false) as assign_score_above_max,

    -- less than 5 score checks
    if(
        assignment_category_code = 'W' and is_missing = 0 and scorepoints < 5,
        true,
        false
    ) as assign_w_score_less_5,

    if(
        assignment_category_code = 'H' and is_missing = 0 and scorepoints < 5,
        true,
        false
    ) as assign_h_score_less_5,

    if(
        assignment_category_code = 'F' and is_missing = 0 and scorepoints < 5,
        true,
        false
    ) as assign_f_score_less_5,

    -- miss assign not score 5 for non-hs
    if(
        assignment_category_code = 'W'
        and school_level != 'HS'
        and is_missing = 1
        and scorepoints != 5,
        true,
        false
    ) as assign_w_missing_score_not_5,

    if(
        assignment_category_code = 'H'
        and school_level != 'HS'
        and is_missing = 1
        and scorepoints != 5,
        true,
        false
    ) as assign_h_missing_score_not_5,

    if(
        assignment_category_code = 'F'
        and school_level != 'HS'
        and is_missing = 1
        and scorepoints != 5,
        true,
        false
    ) as assign_f_missing_score_not_5,

    -- miss assign not score 0 for hs
    if(
        assignment_category_code = 'W'
        and school_level = 'HS'
        and is_missing = 1
        and scorepoints != 0,
        true,
        false
    ) as assign_w_missing_score_not_0,

    if(
        assignment_category_code = 'H'
        and school_level = 'HS'
        and is_missing = 1
        and scorepoints != 0,
        true,
        false
    ) as assign_h_missing_score_not_0,

    if(
        assignment_category_code = 'F'
        and school_level = 'HS'
        and is_missing = 1
        and scorepoints != 0,
        true,
        false
    ) as assign_f_missing_score_not_0,

    -- 50% s assign min
    if(
        assignment_category_code = 'S' and scorepoints < (totalpointvalue / 2),
        true,
        false
    ) as assign_s_score_less_50p,

    -- conversion chart
    if(
        is_exempt = 0
        and school_level = 'MS'
        and assignment_category_code = 'S'
        and assign_final_score_percent is not null
        and assign_final_score_percent
        not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
        true,
        false
    ) as assign_s_ms_score_not_conversion_chart_options,

    if(
        is_exempt = 0
        and school_level = 'HS'
        and assignment_category_code = 'S'
        and not is_ap_course
        and assign_final_score_percent is not null
        and assign_final_score_percent
        not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100),
        true,
        false
    ) as assign_s_hs_score_not_conversion_chart_options,

from roster_assignments_scores
