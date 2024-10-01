with
    filtered_sections as (
        select
            _dbt_source_relation,
            terms_yearid,
            sections_schoolid,
            sections_id,
            sections_dcid,
            terms_firstday,
            terms_lastday,
            sections_course_number,
            teachernumber,

            case
                when
                    concat(sections_schoolid, sections_course_number) in (
                        '73252SEM72250G1',
                        '73252SEM72250G2',
                        '73252SEM72250G3',
                        '73252SEM72250G4',
                        '133570965SEM72250G1',
                        '133570965SEM72250G2',
                        '133570965SEM72250G3',
                        '133570965SEM72250G4',
                        '133570965LOG300',
                        '73252LOG300',
                        '73258LOG300',
                        '732514LOG300',
                        '732513LOG300',
                        '732514GYM08035G1',
                        '732514GYM08036G2',
                        '732514GYM08037G3',
                        '732514GYM08038G4'
                    )
                then true
                else false
            end as exclude_from_audit,
        from {{ ref("base_powerschool__sections") }}
        where
            courses_course_number not in (
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

    assignments as (
        select
            sec._dbt_source_relation,
            sec.sections_id as sectionid,
            sec.teachernumber as teacher_number,
            sec.terms_yearid as yearid,

            c.semester,
            c.quarter,
            c.week_number_quarter,
            c.week_start_monday,
            c.week_end_sunday,
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
                    c.quarter,
                    c.week_number_quarter,
                    ge.assignment_category_code
            ) as total_expected_section_quarter_week_category,

            sum(asg.n_expected_scored) over (
                partition by
                    sec._dbt_source_relation,
                    sec.sections_id,
                    c.quarter,
                    c.week_number_quarter,
                    ge.assignment_category_code
            ) as total_expected_scored_section_quarter_week_category,

            sum(asg.n_expected) over (
                partition by
                    sec._dbt_source_relation,
                    sec.teachernumber,
                    sec.sections_schoolid,
                    c.quarter,
                    c.week_number_quarter,
                    ge.assignment_category_code
            ) as total_expected_teacher_school_quarter_week_category,

            sum(asg.n_expected_scored) over (
                partition by
                    sec._dbt_source_relation,
                    sec.teachernumber,
                    sec.sections_schoolid,
                    c.quarter,
                    c.week_number_quarter,
                    ge.assignment_category_code
            ) as total_expected_scored_teacher_school_quarter_week_category,
        from {{ ref("int_powerschool__calendar_week") }} as c
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on c.academic_year = ge.academic_year
            and c.region = ge.region
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
            and c.school_level = ge.school_level
        left join
            filtered_sections as sec
            on c.schoolid = sec.sections_schoolid
            and c.yearid = sec.terms_yearid
            and c.week_end_date between sec.terms_firstday and sec.terms_lastday
            and {{ union_dataset_join_clause(left_alias="c", right_alias="sec") }}
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on sec.sections_dcid = a.sectionsdcid
            and {{ union_dataset_join_clause(left_alias="sec", right_alias="a") }}
            and ge.assignment_category_name = a.category_name
            and a.duedate between c.week_start_monday and c.week_end_sunday
        left join
            {{ ref("int_powerschool__assignment_score_rollup") }} as asg
            on a.assignmentsectionid = asg.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
        where
            not sec.exclude_from_audit
            -- leaves only WH category for iReady courses
            and concat(sec.sections_course_number, ge.assignment_category_code) not in (
                'SEM72005G1F',
                'SEM72005G2F',
                'SEM72005G3F',
                'SEM72005G4F',
                'SEM72005G1S',
                'SEM72005G2S',
                'SEM72005G3S',
                'SEM72005G4S'
            )
            and sec.terms_firstday >= '{{ var("current_academic_year") }}-07-01'
    )

select
    _dbt_source_relation,
    sectionid,
    teacher_number,
    `quarter`,
    semester,
    week_number_quarter,
    week_start_monday,
    week_end_sunday,
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
    n_students,
    n_late,
    n_exempt,
    n_missing,
    n_expected,
    n_expected_scored,

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
        assignment_category_code = 'W'
        and assignment_count_section_quarter_category_running_week < expectation,
        true,
        false
    ) as w_expected_assign_count_not_met,

    if(
        assignment_category_code = 'F'
        and assignment_count_section_quarter_category_running_week < expectation,
        true,
        false
    ) as f_expected_assign_count_not_met,

    if(
        assignment_category_code = 'S'
        and assignment_count_section_quarter_category_running_week < expectation,
        true,
        false
    ) as s_expected_assign_count_not_met,

    if(
        assignment_category_code = 'W' and totalpointvalue != 10, true, false
    ) as w_assign_max_score_not_10,

    if(
        assignment_category_code = 'F' and totalpointvalue != 10, true, false
    ) as f_assign_max_score_not_10,

    if(
        total_missing_section_quarter = 0, true, false
    ) as qt_teacher_no_missing_assignments,

    if(
        assignment_category_code = 'S'
        and n_expected >= 1
        and total_totalpointvalue_section_quarter < 200,
        true,
        false
    ) as qt_teacher_s_total_less_200,

    if(
        assignment_category_code = 'S'
        and n_expected = 1
        and total_totalpointvalue_section_quarter > 200,
        true,
        false
    ) as qt_teacher_s_total_greater_200,

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
