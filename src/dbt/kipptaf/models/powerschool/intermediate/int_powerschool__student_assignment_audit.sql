with
    filtered_courses as (
        select
            _dbt_source_relation,
            cc_academic_year,
            cc_yearid,
            cc_schoolid,
            students_dcid,
            cc_studentid,
            cc_course_number,
            cc_sectionid,
            sections_dcid,
            cc_dateenrolled,
            cc_dateleft,

            case  -- noqa: ST02
                when  -- noqa: ST02
                    concat(cc_schoolid, cc_course_number) in (  -- noqa: ST02
                        '73252SEM72250G1',  -- noqa: ST02
                        '73252SEM72250G2',  -- noqa: ST02
                        '73252SEM72250G3',  -- noqa: ST02
                        '73252SEM72250G4',  -- noqa: ST02
                        '133570965SEM72250G1',  -- noqa: ST02
                        '133570965SEM72250G2',  -- noqa: ST02
                        '133570965SEM72250G3',  -- noqa: ST02
                        '133570965SEM72250G4',  -- noqa: ST02
                        '133570965LOG300',  -- noqa: ST02
                        '73252LOG300',  -- noqa: ST02
                        '73258LOG300',  -- noqa: ST02
                        '732514LOG300',  -- noqa: ST02
                        '732513LOG300',  -- noqa: ST02
                        '732514GYM08035G1',  -- noqa: ST02
                        '732514GYM08036G2',  -- noqa: ST02
                        '732514GYM08037G3',  -- noqa: ST02
                        '732514GYM08038G4'  -- noqa: ST02
                    )  -- noqa: ST02
                then true  -- noqa: ST02
                else false  -- noqa: ST02
            end as exclude_from_audit,  -- noqa: ST02
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            cc_sectionid > 0
            and courses_course_number not in (
                'LOG100',  -- Lunch
                'LOG1010',  -- Lunch
                'LOG11',  -- Lunch
                'LOG12',  -- Lunch
                'LOG20',  -- Early Dismissal
                'LOG22999XL',  -- Lunch
                'LOG300',  -- Study Hall
                'LOG9',  -- Lunch
                'SEM22106G1',  -- Advisory
                'SEM22106S1',  -- Not in SY24-25 yet
                'SEM22101G1'  -- Student Government
            )
    ),

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

            ge.assignment_category_code,
            ge.assignment_category_term,
            ge.expectation,

            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,
            a.category_name,

            s.scorepoints,
            s.actualscoreentered,
            if(s.islate in (0, null), false, true) as islate,
            if(s.isexempt in (0, null), false, true) as isexempt,
            if(s.ismissing in (0, null), false, true) as ismissing,

        from filtered_courses as ce
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
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on c.academic_year = ge.academic_year
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
            and c.region = ge.region
            and sch.school_level = ge.school_level
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on ce.sections_dcid = a.sectionsdcid
            and ce.cc_dateenrolled <= a.duedate
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="a") }}
            and a.duedate between c.week_start_date and c.week_end_date
            and {{ union_dataset_join_clause(left_alias="c", right_alias="a") }}
            and ge.assignment_category_name = a.category_name
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
            and not ce.exclude_from_audit
            -- leaves only WH category for iReady courses
            and concat(ce.cc_course_number, ge.assignment_category_code) not in (
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
    category_name,
    assignment_category_term,
    assignmentid,
    assignment_name,
    duedate,
    scoretype,
    totalpointvalue,
    actualscoreentered,
    scorepoints,

    safe_divide(scorepoints, totalpointvalue) * 100 as assign_final_score_percent,

    if(isexempt, 1, 0) as isexempt,
    if(islate, 1, 0) as islate,
    if(ismissing, 1, 0) as ismissing,

    if(scorepoints > totalpointvalue, true, false) as assign_score_above_max,

    if(
        assignmentid is not null and not isexempt, true, false
    ) as assign_expected_to_be_scored,

    if(
        assignmentid is not null and scorepoints is not null and not isexempt,
        true,
        false
    ) as assign_scored,

    if(
        assignmentid is not null and scorepoints is null and not isexempt, true, false
    ) as assign_null_score,

    if(
        assignmentid is not null
        and not isexempt
        and ((not ismissing and scorepoints is not null) or scorepoints is not null),
        true,
        false
    ) as assign_expected_with_score,

    if(isexempt and scorepoints > 0, true, false) as assign_exempt_with_score,

    if(
        assignment_category_code = 'W' and scorepoints < 5, true, false
    ) as assign_w_score_less_5,

    if(
        assignment_category_code = 'F' and scorepoints < 5, true, false
    ) as assign_f_score_less_5,

    if(
        assignment_category_code = 'W' and ismissing and scorepoints != 5, true, false
    ) as assign_w_missing_score_not_5,

    if(
        assignment_category_code = 'F' and ismissing and scorepoints != 5, true, false
    ) as assign_f_missing_score_not_5,

    if(
        assignment_category_code = 'S' and scorepoints < (totalpointvalue / 2),
        true,
        false
    ) as assign_s_score_less_50p,
from students_assignments
