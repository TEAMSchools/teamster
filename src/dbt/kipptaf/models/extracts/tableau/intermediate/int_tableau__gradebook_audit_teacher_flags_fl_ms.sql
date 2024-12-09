{{- config(materialized="table") -}}

with
    teacher_assignments as (
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

            ge.region,
            ge.school_level,
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

            if(
                ge.assignment_category_code = 'W' and a.totalpointvalue != 10,
                true,
                false
            ) as w_assign_max_score_not_10,

            if(
                ge.assignment_category_code = 'F' and a.totalpointvalue != 10,
                true,
                false
            ) as f_assign_max_score_not_10,

            if(
                ge.region = 'Miami'
                and ge.assignment_category_code = 'S'
                and a.totalpointvalue > 100,
                true,
                false
            ) as s_max_score_greater_100,

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

        from {{ ref("int_powerschool__calendar_week") }} as c
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on c.academic_year = ge.academic_year
            and c.region = ge.region
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
            and c.school_level = ge.school_level
        left join
            {{ ref("base_powerschool__sections") }} as sec
            on c.schoolid = sec.sections_schoolid
            and c.yearid = sec.terms_yearid
            and c.week_end_date between sec.terms_firstday and sec.terms_lastday
            and {{ union_dataset_join_clause(left_alias="c", right_alias="sec") }}
            /* exclude courses */
            and sec.courses_course_number not in (
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
            sec.terms_firstday >= '2024-07-01'
            and ge.region = 'Miami'
            and ge.school_level = 'MS'
            and c.school_week_start_date_lead <= current_date('America/New_York')

    ),

    calculations as (
        select
            _dbt_source_relation,
            region,
            school_level,
            yearid,
            semester,
            quarter,
            week_number_quarter,
            week_start_monday,
            week_end_sunday,
            school_week_start_date_lead,
            teacher_number,
            sectionid,
            assignment_category_code,
            assignment_category_name,
            assignment_category_term,
            expectation,

            assignmentid,
            assignment_name,
            duedate,
            scoretype,
            totalpointvalue,
            n_students,
            n_late,
            n_exempt,
            n_missing,
            n_expected,
            n_expected_scored,
            total_totalpointvalue_section_quarter,
            total_missing_section_quarter,
            w_assign_max_score_not_10,
            f_assign_max_score_not_10,
            s_max_score_greater_100,

            if(
                assignment_category_code = 'S'
                and n_expected = 1
                and total_totalpointvalue_section_quarter > 200,
                true,
                false
            ) as qt_teacher_s_total_greater_200,

            if(
                total_missing_section_quarter = 0, true, false
            ) as qt_teacher_no_missing_assignments,

            if(
                assignment_category_code = 'W'
                and assignment_count_section_quarter_category_running_week
                < expectation,
                true,
                false
            ) as w_expected_assign_count_not_met,

            if(
                assignment_category_code = 'F'
                and assignment_count_section_quarter_category_running_week
                < expectation,
                true,
                false
            ) as f_expected_assign_count_not_met,

            if(
                assignment_category_code = 'S'
                and assignment_count_section_quarter_category_running_week
                < expectation,
                true,
                false
            ) as s_expected_assign_count_not_met,

        from teacher_assignments
    ),

    -- class + category: qt_teacher_s_total_greater_200,
    -- w_expected_assign_count_not_met,
    -- f_expected_assign_count_not_met, s_expected_assign_count_not_met,
    -- qt_teacher_no_missing_assignments
    class_category as (
        select distinct
            _dbt_source_relation,
            yearid,
            semester,
            quarter,
            week_number_quarter,
            week_start_monday,
            week_end_sunday,
            school_week_start_date_lead,
            teacher_number,
            sectionid,
            assignment_category_code,
            assignment_category_name,
            assignment_category_term,
            expectation,

            qt_teacher_s_total_greater_200,
            w_expected_assign_count_not_met,
            f_expected_assign_count_not_met,
            s_expected_assign_count_not_met,

        from calculations
        where
            yearid = {{ var("current_academic_year") - 1990 }}
            and region = 'Miami'
            and school_level = 'MS'
    ),

    -- class + category: qt_teacher_s_total_greater_200,
    -- w_expected_assign_count_not_met,
    -- f_expected_assign_count_not_met, s_expected_assign_count_not_met,
    -- qt_teacher_no_missing_assignments
    class_category_assign as (
        select distinct
            _dbt_source_relation,
            yearid,
            semester,
            quarter,
            week_number_quarter,
            week_start_monday,
            week_end_sunday,
            school_week_start_date_lead,
            teacher_number,
            sectionid,
            assignment_category_code,
            assignment_category_name,
            assignment_category_term,
            expectation,

            assignmentid,
            assignment_name,
            duedate,
            scoretype,
            totalpointvalue,
            w_assign_max_score_not_10,
            f_assign_max_score_not_10,
            s_max_score_greater_100,

        from calculations
        where
            yearid = {{ var("current_academic_year") - 1990 }}
            and region = 'Miami'
            and school_level = 'MS'
            and assignmentid is not null
    )

select
    _dbt_source_relation,
    semester,
    quarter,
    week_number_quarter,
    teacher_number,
    sectionid,
    assignment_category_code,
    assignment_category_name,

    null as assignmentid,
    cast(null as date) duedate,
    '' as scoretype,
    null totalpointvalue,

    'Teacher Class Category' as groupings,

    audit_flag_name,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    class_category unpivot (
        audit_flag_value for audit_flag_name in (
            qt_teacher_s_total_greater_200,
            w_expected_assign_count_not_met,
            f_expected_assign_count_not_met,
            s_expected_assign_count_not_met
        )
    )
where audit_flag_value

union all

select
    _dbt_source_relation,
    semester,
    quarter,
    week_number_quarter,
    teacher_number,
    sectionid,
    assignment_category_code,
    assignment_category_name,

    assignmentid,
    duedate,
    scoretype,
    totalpointvalue,

    'Teacher Class Category Assignment' as groupings,

    audit_flag_name,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    class_category_assign unpivot (
        audit_flag_value for audit_flag_name in (
            w_assign_max_score_not_10,
            f_assign_max_score_not_10,
            s_max_score_greater_100
        )
    )
where audit_flag_value
