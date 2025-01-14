{{- config(materialized="table") -}}

with
    roster_assignments_scores as (
        select
            ce._dbt_source_relation,
            ce.studentid,
            ce.sectionid,
            ce.school_level,
            ce.region,
            ce.quarter,
            ce.semester,
            ce.week_number_quarter,
            ce.week_number_academic_year,
            ce.week_start_monday,
            ce.week_end_sunday,
            ce.school_week_start_date_lead,
            ce.assignment_category_term,
            ce.assignment_category_code,
            ce.assignment_category_name,
            ce.is_ap_course,

            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,
            a.category_name,

            s.scorepoints as raw_score,
            s.actualscoreentered,

            coalesce(s.islate, 0) as is_late,
            coalesce(s.isexempt, 0) as is_exempt,
            coalesce(s.ismissing, 0) as is_missing,

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
        from {{ ref("int_tableau__gradebook_audit_roster") }} as ce
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on ce.sections_dcid = a.sectionsdcid
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
        where
            /* exclude courses by school */
            ce.schoolid_course_number not in (
                '133570965LOG300',
                '133570965SEM72250G1',
                '133570965SEM72250G2',
                '133570965SEM72250G3',
                '133570965SEM72250G4',
                '732514GYM08035G1',
                '732514GYM08036G2',
                '732514GYM08037G3',
                '732514GYM08038G4',
                '73252SEM72250G1',
                '73252SEM72250G2',
                '73252SEM72250G3',
                '73252SEM72250G4'
            )
            /* exclude F & S categories for iReady courses */
            and ce.course_number_assignment_category_code not in (
                'SEM72005G1F',
                'SEM72005G2F',
                'SEM72005G3F',
                'SEM72005G4F',
                'SEM72005G1S',
                'SEM72005G2S',
                'SEM72005G3S',
                'SEM72005G4S'
            )
    )

select
    _dbt_source_relation,
    studentid,
    sectionid,
    `quarter`,
    semester,
    week_number_academic_year,
    week_number_quarter,
    week_start_monday,
    week_end_sunday,
    school_week_start_date_lead,
    school_level,
    assignment_category_term,
    assignment_category_code,
    assignment_category_name,
    assignmentid,
    assignment_name,
    duedate,
    scoretype,
    totalpointvalue,
    raw_score,
    score_entered,
    assign_final_score_percent,
    is_exempt,
    is_late,
    is_missing,

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

    if(raw_score > totalpointvalue, true, false) as assign_score_above_max,

    if(
        assignmentid is not null and is_exempt = 0, true, false
    ) as assign_expected_to_be_scored,

    if(
        assignmentid is not null and raw_score is not null and is_exempt = 0,
        true,
        false
    ) as assign_scored,

    if(
        assignmentid is not null and raw_score is null and is_exempt = 0, true, false
    ) as assign_null_score,

    if(
        assignmentid is not null
        and is_exempt = 0
        and ((is_missing = 0 and raw_score is not null) or raw_score is not null),
        true,
        false
    ) as assign_expected_with_score,

    if(is_exempt = 1 and raw_score > 0, true, false) as assign_exempt_with_score,

    if(
        assignment_category_code = 'W' and raw_score < 5, true, false
    ) as assign_w_score_less_5,

    if(
        assignment_category_code = 'F' and raw_score < 5, true, false
    ) as assign_f_score_less_5,

    if(
        assignment_category_code = 'W' and is_missing = 1 and raw_score != 5,
        true,
        false
    ) as assign_w_missing_score_not_5,

    if(
        assignment_category_code = 'F' and is_missing = 1 and raw_score != 5,
        true,
        false
    ) as assign_f_missing_score_not_5,

    if(
        assignment_category_code = 'S' and raw_score < (totalpointvalue / 2),
        true,
        false
    ) as assign_s_score_less_50p,
from roster_assignments_scores
