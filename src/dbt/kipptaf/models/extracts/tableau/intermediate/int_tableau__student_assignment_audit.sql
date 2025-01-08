{{- config(materialized="table") -}}

with
    students_assignments as (
        select
            ce._dbt_source_relation,
            ce.cc_studentid as studentid,
            ce.cc_sectionid as sectionid,

            sch.school_level,

            c.region,
            c.quarter,
            c.semester,
            c.week_number_quarter,
            c.week_number_academic_year,
            c.week_start_monday,
            c.week_end_sunday,
            c.school_week_start_date_lead,

            a.category_code as assignment_category_code,
            a.category_name as assignment_category_name,
            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,
            a.category_name,

            s.scorepoints as raw_score,
            s.actualscoreentered,

            if(ce.ap_course_subject is not null, true, false) as is_ap_course,

            if(s.islate = 0 or s.islate is null, false, true) as islate,
            if(s.isexempt = 0 or s.isexempt is null, false, true) as isexempt,
            if(s.ismissing = 0 or s.ismissing is null, false, true) as ismissing,

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
        from {{ ref("base_powerschool__course_enrollments") }} as ce
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on ce.cc_schoolid = sch.school_number
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="sch") }}
        inner join
            {{ ref("int_powerschool__calendar_week") }} as c
            on ce.cc_schoolid = c.schoolid
            and ce.cc_yearid = c.yearid
            and c.week_end_date between ce.cc_dateenrolled and ce.cc_dateleft
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="c") }}
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on ce.sections_dcid = a.sectionsdcid
            and ce.cc_dateenrolled <= a.duedate
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="a") }}
            and a.duedate between c.week_start_date and c.week_end_date
            and {{ union_dataset_join_clause(left_alias="c", right_alias="a") }}
            and a.iscountedinfinalgrade = 1
            and a.scoretype in ('POINTS', 'PERCENT')
        left join
            {{ ref("stg_powerschool__assignmentscore") }} as s
            on ce.students_dcid = s.studentsdcid
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="s") }}
            and a.assignmentsectionid = s.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
        where
            ce.cc_academic_year = {{ var("current_academic_year") }}
            and ce.cc_sectionid > 0
            /* exclude courses */
            and ce.courses_course_number not in (
                'LOG20',  -- Early Dismissal
                'LOG300',  -- Study Hall
                'SEM22101G1',  -- Student Government
                'SEM22106G1',  -- Advisory
                'SEM22106S1',  -- Not in SY24-25 yet
                /* Lunch */
                'LOG100',
                'LOG1010',
                'LOG11',
                'LOG12',
                'LOG22999XL',
                'LOG9'
            )
            /* exclude courses by school */
            and concat(ce.cc_schoolid, ce.cc_course_number) not in (
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
            and concat(ce.cc_course_number, a.category_code) not in (
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

    if(isexempt, 1, 0) as is_exempt,
    if(islate, 1, 0) as is_late,
    if(ismissing, 1, 0) as is_missing,

    if(
        not isexempt
        and school_level = 'MS'
        and assignment_category_code = 'S'
        and assign_final_score_percent is not null
        and assign_final_score_percent
        not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
        true,
        false
    ) as assign_s_ms_score_not_conversion_chart_options,

    if(
        not isexempt
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
        assignmentid is not null and not isexempt, true, false
    ) as assign_expected_to_be_scored,

    if(
        assignmentid is not null and raw_score is not null and not isexempt, true, false
    ) as assign_scored,

    if(
        assignmentid is not null and raw_score is null and not isexempt, true, false
    ) as assign_null_score,

    if(
        assignmentid is not null
        and not isexempt
        and ((not ismissing and raw_score is not null) or raw_score is not null),
        true,
        false
    ) as assign_expected_with_score,

    if(isexempt and raw_score > 0, true, false) as assign_exempt_with_score,

    if(
        assignment_category_code = 'W' and raw_score < 5, true, false
    ) as assign_w_score_less_5,

    if(
        assignment_category_code = 'F' and raw_score < 5, true, false
    ) as assign_f_score_less_5,

    if(
        assignment_category_code = 'W' and ismissing and raw_score != 5, true, false
    ) as assign_w_missing_score_not_5,

    if(
        assignment_category_code = 'F' and ismissing and raw_score != 5, true, false
    ) as assign_f_missing_score_not_5,

    if(
        assignment_category_code = 'S' and raw_score < (totalpointvalue / 2),
        true,
        false
    ) as assign_s_score_less_50p,
from students_assignments
