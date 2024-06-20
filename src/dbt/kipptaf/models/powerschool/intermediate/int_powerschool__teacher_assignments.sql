with
    sections as (
        select
            sec._dbt_source_relation,
            sec.sections_dcid,
            sec.sections_id as section_id,
            sec.sections_schoolid as schoolid,
            sec.sections_course_number as course_number,
            sec.teachernumber as teacher_number,
            sec.teacher_lastfirst,
            sec.terms_yearid as yearid,
            sec.terms_firstday,
            sec.terms_lastday,

            sec.terms_yearid + 1990 as academic_year,
            initcap(regexp_extract(sec._dbt_source_relation, r'kipp(\w+)_')) as region,

            case
                sch.high_grade when 4 then 'ES' when 8 then 'MS' when 12 then 'HS'
            end as grade_band,

            if(
                sch.high_grade in (4, 8),
                sec.sections_section_number,
                sec.sections_external_expression
            ) as section_or_period,
        from {{ ref("base_powerschool__sections") }} as sec
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sec.sections_schoolid = sch.school_number
            and {{ union_dataset_join_clause(left_alias="sec", right_alias="sch") }}
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
    ),

    valid_sections as (
        select
            _dbt_source_relation,
            sections_dcid,
            section_id,
            schoolid,
            section_or_period,
            course_number,
            teacher_number,
            teacher_lastfirst,
            yearid,
            academic_year,
            terms_firstday,
            terms_lastday,
            region,
            grade_band,
        from sections
        where region = 'Miami'

        union all

        select
            _dbt_source_relation,
            sections_dcid,
            section_id,
            schoolid,
            section_or_period,
            course_number,
            teacher_number,
            teacher_lastfirst,
            yearid,
            academic_year,
            terms_firstday,
            terms_lastday,
            region,
            grade_band,
        from sections
        where grade_band in ('MS', 'HS') and region != 'Miami'
    ),

    expectations as (
        select
            vs._dbt_source_relation,
            vs.sections_dcid,
            vs.section_id,
            vs.schoolid,
            vs.section_or_period,
            vs.course_number,
            vs.teacher_number,
            vs.teacher_lastfirst,
            vs.yearid,
            vs.academic_year,
            vs.terms_firstday,
            vs.terms_lastday,
            vs.region,
            vs.grade_band,

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
            ge.expectation,
        from valid_sections as vs
        inner join
            {{ ref("int_powerschool__calendar_week") }} as c
            on vs.schoolid = c.schoolid
            and vs.yearid = c.yearid
            and c.week_end_date between vs.terms_firstday and vs.terms_lastday
            and {{ union_dataset_join_clause(left_alias="vs", right_alias="c") }}
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on c.academic_year = ge.academic_year
            and c.region = ge.region
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
    ),

    assignments as (
        select
            t._dbt_source_relation,
            t.teacher_number,
            t.teacher_lastfirst,
            t.course_number,
            t.section_id,
            t.sections_dcid,
            t.section_or_period,
            t.yearid,
            t.academic_year,
            t.region,
            t.grade_band,
            t.schoolid,
            t.semester,
            t.quarter,
            t.week_number_academic_year,
            t.week_number_quarter,
            t.week_start_date,
            t.week_end_date,
            t.school_week_start_date_lead,
            t.assignment_category_code,
            t.assignment_category_name,
            t.expectation,

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

            count(a.assignmentid) over (
                partition by
                    t._dbt_source_relation,
                    t.section_id,
                    t.quarter,
                    t.assignment_category_code
                order by t.week_number_quarter asc
            ) as assignment_count_section_quarter_category_running_week,

            sum(a.totalpointvalue) over (
                partition by t._dbt_source_relation, t.section_id, t.quarter
            ) as total_totalpointvalue_section_quarter,

            sum(asg.n_missing) over (
                partition by t._dbt_source_relation, t.section_id, t.quarter
            ) as total_missing_section_quarter,

            sum(asg.n_expected) over (
                partition by
                    t._dbt_source_relation,
                    t.section_id,
                    t.week_number_quarter,
                    t.assignment_category_code
            ) as total_expected_section_quarter_week_category,

            sum(asg.n_expected_scored) over (
                partition by
                    t._dbt_source_relation,
                    t.section_id,
                    t.week_number_quarter,
                    t.assignment_category_code
            ) as total_expected_scored_section_quarter_week_category,

            sum(asg.n_expected) over (
                partition by
                    t._dbt_source_relation,
                    t.teacher_number,
                    t.schoolid,
                    t.week_number_quarter,
                    t.assignment_category_code
            ) as total_expected_teacher_school_quarter_week_category,

            sum(asg.n_expected_scored) over (
                partition by
                    t._dbt_source_relation,
                    t.teacher_number,
                    t.schoolid,
                    t.week_number_quarter,
                    t.assignment_category_code
            ) as total_expected_scored_teacher_school_quarter_week_category,
        from expectations as t
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on t.sections_dcid = a.sectionsdcid
            and t.assignment_category_name = a.category_name
            and a.duedate between t.week_start_date and t.week_end_date
            and {{ union_dataset_join_clause(left_alias="t", right_alias="a") }}
        left join
            {{ ref("int_powerschool__assignment_score_rollup") }} as asg
            on a.assignmentsectionid = asg.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="asg") }}
    )

select
    _dbt_source_relation,
    yearid,
    academic_year,
    region,
    schoolid,
    grade_band as school_level,
    teacher_number,
    teacher_lastfirst as teacher_name,
    course_number,
    section_or_period,
    section_id as sectionid,
    sections_dcid,
    semester as teacher_semester_code,
    `quarter` as teacher_quarter,
    week_number_academic_year as audit_yr_week_number,
    week_number_quarter as audit_qt_week_number,
    week_start_date as audit_start_date,
    week_end_date as audit_end_date,
    school_week_start_date_lead as audit_due_date,
    assignment_category_code as expected_teacher_assign_category_code,
    assignment_category_name as expected_teacher_assign_category_name,
    expectation as audit_category_exp_audit_week_ytd,
    assignmentid as teacher_assign_id,
    assignment_name as teacher_assign_name,
    scoretype as teacher_assign_score_type,
    totalpointvalue as teacher_assign_max_score,
    duedate as teacher_assign_due_date,
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
    ) as qt_teacher_s_total_less_200,

    if(
        n_expected = 1 and total_totalpointvalue_section_quarter > 200, true, false
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
