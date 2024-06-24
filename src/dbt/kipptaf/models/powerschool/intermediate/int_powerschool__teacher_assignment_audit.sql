with
    assignments as (
        select
            sec._dbt_source_relation,
            sec.sections_id as sectionid,
            sec.teachernumber as teacher_number,
            sec.terms_yearid as yearid,

            c.semester,
            c.quarter,
            c.week_number_quarter,
            c.week_number_academic_year,
            c.week_start_date,
            c.week_end_date,
            c.school_week_start_date,
            c.school_week_end_date,
            c.school_week_start_date_lead,

            ge.assignment_category_code,
            ge.assignment_category_name,
            ge.assignment_category_term,
            ge.expectation,

            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,

            asg.n_students,
            asg.n_late,
            asg.n_exempt,
            asg.n_missing,
            asg.n_expected,
            asg.n_expected_scored,
            asg.avg_expected_scored_percent,

            sum(a.totalpointvalue) over (
                partition by sec._dbt_source_relation, sec.sections_id, c.quarter
            ) as total_totalpointvalue_section_quarter,

            sum(asg.n_missing) over (
                partition by sec._dbt_source_relation, sec.sections_id, c.quarter
            ) as total_missing_section_quarter,

            count(a.assignmentid) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sections_id,
                    c.quarter,
                    ge.assignment_category_code
                order by c.week_number_quarter asc
            ) as assignment_count_section_quarter_category_running_week,

            sum(asg.n_expected) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sections_id,
                    c.week_number_quarter,
                    ge.assignment_category_code
            ) as total_expected_section_quarter_week_category,

            sum(asg.n_expected_scored) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sections_id,
                    c.week_number_quarter,
                    ge.assignment_category_code
            ) as total_expected_scored_section_quarter_week_category,

            sum(asg.n_expected) over (
                partition by
                    sec._dbt_source_relation,
                    sec.teachernumber,
                    sec.sections_schoolid,
                    c.week_number_quarter,
                    ge.assignment_category_code
            ) as total_expected_teacher_school_quarter_week_category,

            sum(asg.n_expected_scored) over (
                partition by
                    sec._dbt_source_relation,
                    sec.teachernumber,
                    sec.sections_schoolid,
                    c.week_number_quarter,
                    ge.assignment_category_code
            ) as total_expected_scored_teacher_school_quarter_week_category,
        from {{ ref("base_powerschool__sections") }} as sec
        inner join
            {{ ref("int_powerschool__calendar_week") }} as c
            on sec.sections_schoolid = c.schoolid
            and sec.terms_yearid = c.yearid
            and c.week_end_date between sec.terms_firstday and sec.terms_lastday
            and {{ union_dataset_join_clause(left_alias="sec", right_alias="c") }}
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on c.academic_year = ge.academic_year
            and c.region = ge.region
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on sec.sections_dcid = a.sectionsdcid
            and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
            and ge.assignment_category_name = a.category_name
            and a.duedate between c.week_start_date and c.week_end_date
        left join
            {{ ref("int_powerschool__assignment_score_rollup") }} as asg
            on a.assignmentsectionid = asg.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
        where
            sec.sections_course_number not in (
                'HR',
                'LOG100',
                'LOG1010',
                'LOG11',
                'LOG12',
                'LOG20',
                'LOG22999XL',
                'LOG300',
                'LOG9',
                'SEM22106G1',
                'SEM22106S1'
            )
            and sec.terms_firstday >= date({{ var("current_academic_year") }}, 7, 1)
    )

select
    _dbt_source_relation,
    sectionid,
    teacher_number,
    `quarter`,
    semester,
    week_number_academic_year,
    week_number_quarter,
    week_start_date,
    week_end_date,
    school_week_start_date_lead,
    assignment_category_code,
    assignment_category_name,
    assignment_category_term,
    expectation,
    assignmentid,
    assignment_name,
    scoretype,
    totalpointvalue,
    duedate,

    assignment_count_section_quarter_category_running_week
    as teacher_running_total_assign_by_cat,
    avg_expected_scored_percent
    as teacher_avg_score_for_assign_per_class_section_and_assign_id,
    total_expected_scored_teacher_school_quarter_week_category
    as total_expected_actual_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_teacher_school_quarter_week_category
    as total_expected_graded_assignments_by_cat_qt_audit_week_all_courses,
    total_expected_scored_section_quarter_week_category
    as total_expected_actual_graded_assignments_by_course_cat_qt_audit_week,
    total_expected_section_quarter_week_category
    as total_expected_graded_assignments_by_course_cat_qt_audit_week,
    n_expected_scored
    as total_expected_actual_graded_assignments_by_course_assign_id_qt_audit_week,
    n_expected as total_expected_graded_assignments_by_course_assign_id_qt_audit_week,

    if(assignmentid is not null, 1, 0) as teacher_assign_count,

    if(
        assignment_count_section_quarter_category_running_week < expectation,
        true,
        false
    ) as expected_assign_count_not_met,

    if(totalpointvalue != 10, true, false) as assign_max_score_not_10,

    if(totalpointvalue > 100, true, false) as max_score_greater_100,

    if(
        total_missing_section_quarter = 0, true, false
    ) as qt_teacher_no_missing_assignments,

    if(
        n_expected >= 1 and total_totalpointvalue_section_quarter < 200, true, false
    ) as qt_teacher_total_less_200,

    if(
        n_expected = 1 and total_totalpointvalue_section_quarter > 200, true, false
    ) as qt_teacher_total_greater_200,

    round(
        safe_divide(
            total_expected_scored_teacher_school_quarter_week_category,
            total_expected_teacher_school_quarter_week_category
        ),
        2
    ) as percent_graded_completion_by_cat_qt_audit_week_all_courses,

    round(
        safe_divide(
            total_expected_scored_section_quarter_week_category,
            total_expected_section_quarter_week_category
        ),
        2
    ) as percent_graded_completion_by_cat_qt_audit_week,

    round(
        safe_divide(n_expected_scored, n_expected), 2
    ) as percent_graded_completion_by_assign_id_qt_audit_week,
from assignments
