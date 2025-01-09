{{- config(materialized="table") -}}

with
    sections as (
        select
            _dbt_source_relation,
            sections_dcid,
            sections_id,
            sections_schoolid,
            sections_course_number,
            teachernumber,
            terms_yearid,
            terms_firstday,
            terms_lastday,
        from {{ ref("base_powerschool__sections") }}
        /* exclude courses */
        where
            courses_course_number not in (
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
            /* exclude courses at specific schools */
            and concat(sections_schoolid, sections_course_number) not in (
                '73252SEM72250G1',
                '73252SEM72250G2',
                '73252SEM72250G3',
                '73252SEM72250G4',
                '133570965SEM72250G1',
                '133570965SEM72250G2',
                '133570965SEM72250G3',
                '133570965SEM72250G4',
                '732514GYM08035G1',
                '732514GYM08036G2',
                '732514GYM08037G3',
                '732514GYM08038G4'
            )
    ),

    assignments as (
        select
            c._dbt_source_relation,
            c.region,
            c.school_level,
            c.academic_year,
            c.yearid,
            c.semester,
            c.quarter,
            c.week_number_quarter,
            c.week_start_monday,
            c.week_end_sunday,
            c.school_week_start_date_lead as audit_due_date,

            ge.assignment_category_code,
            ge.assignment_category_name,
            ge.assignment_category_term,
            ge.expectation,

            sec.sections_id as sectionid,
            sec.teachernumber as teacher_number,

            a.assignmentsectionid,
            a.assignmentid as teacher_assign_id,
            a.name as teacher_assign_name,
            a.duedate as teacher_assign_due_date,
            a.scoretype as teacher_assign_score_type,
            a.totalpointvalue as teacher_assign_max_score,

            asg.n_students,
            asg.n_late,
            asg.n_exempt,
            asg.n_missing,
            asg.n_expected,
            asg.n_expected_scored,
            asg.avg_expected_scored_percent
            as teacher_avg_score_for_assign_per_class_section_and_assign_id,

            count(a.assignmentid) over (
                partition by
                    c._dbt_source_relation,
                    c.quarter,
                    ge.assignment_category_code,
                    sec.sections_id
                order by c.week_number_quarter asc
            ) as teacher_running_total_assign_by_cat,

            sum(a.totalpointvalue) over (
                partition by c._dbt_source_relation, c.quarter, sec.sections_id
            ) as total_totalpointvalue_section_quarter,
        from {{ ref("int_powerschool__calendar_week") }} as c
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on c.academic_year = ge.academic_year
            and c.region = ge.region
            and c.school_level = ge.school_level
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
        left join
            sections as sec
            on c.schoolid = sec.sections_schoolid
            and c.yearid = sec.terms_yearid
            and c.week_end_date between sec.terms_firstday and sec.terms_lastday
            and {{ union_dataset_join_clause(left_alias="c", right_alias="sec") }}
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on sec.sections_dcid = a.sectionsdcid
            and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
            and a.duedate between c.week_start_monday and c.week_end_sunday
            and {{ union_dataset_join_clause(left_alias="a", right_alias="c") }}
            and ge.assignment_category_name = a.category_name
        left join
            {{ ref("int_powerschool__assignment_score_rollup") }} as asg
            on a.assignmentsectionid = asg.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
        where
            c.yearid = {{ var("current_academic_year") - 1990 }}
            /* exclude F & S categories for iReady courses */
            and concat(sec.sections_course_number, a.category_code) not in (
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
    region,
    sectionid,
    teacher_number,
    `quarter`,
    semester,
    week_number_quarter,
    week_start_monday,
    week_end_sunday,
    audit_due_date,
    assignment_category_code,
    assignment_category_name,
    assignment_category_term,
    expectation,
    assignmentsectionid,
    teacher_assign_id,
    teacher_assign_name,
    teacher_assign_score_type,
    teacher_assign_max_score,
    teacher_assign_due_date,
    n_students,
    n_late,
    n_exempt,
    n_missing,
    n_expected,
    n_expected_scored,
    teacher_running_total_assign_by_cat,
    teacher_avg_score_for_assign_per_class_section_and_assign_id,

    if(teacher_assign_id is not null, 1, 0) as teacher_assign_count,

    if(
        assignment_category_code = 'W'
        and teacher_running_total_assign_by_cat < expectation,
        true,
        false
    ) as w_expected_assign_count_not_met,

    if(
        assignment_category_code = 'F'
        and teacher_running_total_assign_by_cat < expectation,
        true,
        false
    ) as f_expected_assign_count_not_met,

    if(
        assignment_category_code = 'S'
        and teacher_running_total_assign_by_cat < expectation,
        true,
        false
    ) as s_expected_assign_count_not_met,

    if(
        assignment_category_code = 'W' and teacher_assign_max_score != 10, true, false
    ) as w_assign_max_score_not_10,

    if(
        assignment_category_code = 'F' and teacher_assign_max_score != 10, true, false
    ) as f_assign_max_score_not_10,

    if(
        assignment_category_code = 'S'
        and n_expected = 1
        and total_totalpointvalue_section_quarter > 200,
        true,
        false
    ) as qt_teacher_s_total_greater_200,

    if(
        region = 'Miami'
        and assignment_category_code = 'S'
        and teacher_assign_max_score > 100,
        true,
        false
    ) as s_max_score_greater_100,
from assignments
