{%- set exempt_courses = [
    "LOG20",
    "LOG22999XL",
    "LOG9",
    "LOG100",
    "LOG1010",
    "LOG11",
    "LOG12",
    "LOG300",
    "SEM22106G1",
    "SEM22106S1",
    "HR",
] -%}

with
    calendar as (
        select
            cd._dbt_source_relation,
            cd.schoolid,
            cd.week_start_date,
            cd.week_end_date,

            t.yearid,
            t.abbreviation as `quarter`,

            min(cd.date_value) as school_week_start_date,
            max(cd.date_value) as school_week_end_date,

            row_number() over (
                partition by
                    cd._dbt_source_relation, cd.schoolid, t.yearid, t.abbreviation
                order by cd.week_start_date asc
            ) as week_number_quarter,
        from {{ ref("stg_powerschool__calendar_day") }} as cd
        inner join
            {{ ref("stg_powerschool__terms") }} as t
            on cd.schoolid = t.schoolid
            and cd.date_value between t.firstday and t.lastday
            and {{ union_dataset_join_clause(left_alias="cd", right_alias="t") }}
            and t.portion = 4
        inner join
            {{ ref("stg_powerschool__cycle_day") }} as cy
            on cd.cycle_day_id = cy.id
            and {{ union_dataset_join_clause(left_alias="cd", right_alias="cy") }}
        inner join
            {{ ref("stg_powerschool__bell_schedule") }} as bs
            on cd.schoolid = bs.schoolid
            and cd.bell_schedule_id = bs.id
            and {{ union_dataset_join_clause(left_alias="cd", right_alias="bs") }}
        where
            cd.insession = 1
            and cd.membershipvalue > 0
            and cd.date_value >= date({{ var("current_academic_year") }}, 7, 1)
        group by
            cd._dbt_source_relation,
            cd.schoolid,
            cd.week_start_date,
            cd.week_end_date,
            t.yearid,
            t.abbreviation
    ),

    students as (
        select
            se._dbt_source_relation,
            se.student_number,
            se.studentid,
            se.students_dcid,
            se.academic_year,
            se.yearid,
            se.region,
            se.school_level,
            se.schoolid,
            se.grade_level,

            c.quarter,
            c.week_number_quarter,
            c.week_start_date,
            c.week_end_date,
            c.school_week_start_date,
            c.school_week_end_date,

            ge.storecode_type,
            ge.expectation,
        from {{ ref("base_powerschool__student_enrollments") }} as se
        inner join
            calendar as c
            on se.schoolid = c.schoolid
            and se.yearid = c.yearid
            and {{ union_dataset_join_clause(left_alias="se", right_alias="c") }}
        left join
            {{ ref("stg_reporting__gradebook_expectations") }} as ge
            on se.academic_year = ge.academic_year
            and se.region = ge.region
            and c.quarter = ge.quarter
            and c.week_number_quarter = ge.week_number
        where
            se.academic_year = {{ var("current_academic_year") }}
            and se.rn_year = 1
            and se.enroll_status = 0
            and se.school_level != 'OD'
    ),

    assign_1 as (
        select
            ce._dbt_source_relation,
            ce.sections_dcid,
            ce.cc_dateenrolled as student_course_entry_date,
            ce.cc_sectionid as sectionid,
            ce.cc_section_number as section_number,
            ce.cc_course_number as course_number,
            ce.teacher_lastfirst as teacher_name,

            se.academic_year,
            se.student_number,
            se.studentid,
            se.students_dcid,
            se.yearid,
            se.region,
            se.schoolid,
            se.grade_level,
            se.school_level,

            gb.category_name as assign_category,

            a.scoretype as assign_score_type,
            a.assignmentid as assign_id,
            a.duedate as assign_due_date,
            a.name as assign_name,
            a.totalpointvalue as assign_max_score,

            s.scorepoints as assign_score_raw,

            aud.audit_start_date,
            aud.audit_end_date,
            aud.audit_due_date,
            aud.year_week_number as audit_yr_week_number,
            aud.quarter_week_number as audit_qt_week_number,

            if(ce.ap_course_subject is null, 0, 1) as ap_course,

            concat('Q', gb.storecode_order) as assign_quarter,
            concat(
                left(gb.category_name, 1), right(gb.storecode, 1)
            ) as assign_category_quarter,

            if(
                concat('Q', gb.storecode_order) in ('Q1', 'Q2'), 'S1', 'S2'
            ) as assign_semester_code,

            coalesce(s.islate, 0) as assign_is_late,
            coalesce(s.isexempt, 0) as assign_is_exempt,
            coalesce(s.ismissing, 0) as assign_is_missing,

            if(
                se.region = 'Miami'
                and se.grade_level <= 4
                and gb.category_name != 'Work Habits',
                left(gb.category_name, 1),
                gb.storecode_type
            ) as assign_category_code,

            if(
                se.grade_level <= 4,
                ce.cc_section_number,
                ce.sections_external_expression
            ) as section_or_period,

            if(
                (se.grade_level > 4 and gb.storecode_type != 'Q')
                or (
                    se.grade_level <= 4
                    and se.region = 'Miami'
                    and gb.storecode_type = 'W'
                )
                or (
                    se.grade_level <= 4
                    and se.region = 'Miami'
                    and gb.storecode_type = 'Q'
                    and left(gb.category_name, 1) in ('F', 'S')
                ),
                0,
                1
            ) as exclude_row,

            if(
                a.scoretype = 'PERCENT',
                ((a.totalpointvalue * s.scorepoints) / 100),
                s.scorepoints
            ) as assign_score_converted,

            if(
                a.assignmentid is not null
                and s.scorepoints is null
                and coalesce(s.isexempt, 0) = 0,
                1,
                0
            ) as assign_null_score,

            if(
                a.assignmentid is not null
                and s.scorepoints is not null
                and coalesce(s.isexempt, 0) = 0,
                1,
                0
            ) as assign_scored,

            if(
                a.assignmentid is not null
                and (
                    (coalesce(s.ismissing, 0) = 0 and s.scorepoints is not null)
                    or s.scorepoints is not null
                )
                and coalesce(s.isexempt, 0) = 0,
                1,
                0
            ) as assign_expected_with_score,

            if(
                a.assignmentid is not null and coalesce(s.isexempt, 0) = 0, 1, 0
            ) as assign_expected_to_be_scored,
        from {{ ref("base_powerschool__course_enrollments") }} as ce
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as se
            on ce.cc_studentid = se.studentid
            and ce.cc_yearid = se.yearid
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="enr") }}
            and se.rn_year = 1
            and se.enroll_status = 0
            and se.school_level != 'OD'
        inner join
            {{ ref("int_powerschool__section_grade_config") }} as gb
            on ce.sections_dcid = gb.sections_dcid
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="gb") }}
            and gb.grading_formula_weighting_type != 'Total_Points'
            and gb.storecode_type != 'H'
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as aud
            on se.academic_year = aud.academic_year
            and se.region = aud.region
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on gb.sections_dcid = a.sectionsdcid
            and gb.category_id = a.category_id
            and a.duedate between gb.term_start_date and gb.term_end_date
            and {{ union_dataset_join_clause(left_alias="gb", right_alias="a") }}
            and a.duedate between aud.audit_start_date and aud.audit_end_date
            and a.duedate between ce.cc_dateenrolled and ce.cc_dateleft
            and a.iscountedinfinalgrade = 1
            and a.scoretype in ('POINTS', 'PERCENT')
        left join
            {{ ref("int_powerschool__gradebook_assignment_scores") }} as s
            on a.assignmentsectionid = s.assignmentsectionid
            and se.students_dcid = s.studentsdcid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
        where
            ce.cc_academic_year = {{ var("current_academic_year") }}
            and not ce.is_dropped_section
            -- trunk-ignore(sqlfluff/LT05)
            and ce.cc_course_number not in ('{{ exempt_courses | join("', '") }}')
            and ce.cc_dateleft >= current_date('America/New_York')
    ),

    assign_2 as (
        select
            _dbt_source_relation,
            yearid,
            academic_year,
            region,
            schoolid,
            school_level,
            studentid,
            students_dcid,
            student_number,
            student_course_entry_date,
            grade_level,
            teacher_name,
            course_number,
            ap_course,
            section_or_period,
            sectionid,
            sections_dcid,
            assign_semester_code,
            assign_quarter,
            assign_category_code,
            assign_category,
            assign_category_quarter,
            assign_id,
            assign_name,
            assign_due_date,
            assign_score_type,
            assign_is_exempt,
            assign_is_late,
            assign_is_missing,
            assign_score_raw,
            assign_score_converted,
            assign_null_score,
            assign_scored,
            assign_expected_with_score,
            assign_expected_to_be_scored,
            assign_max_score,
            audit_yr_week_number,
            audit_qt_week_number,
            audit_start_date,
            audit_end_date,
            audit_due_date,

            safe_divide(
                assign_score_converted, assign_max_score
            ) as assign_final_score_percent,
        from assign_1
        where exclude_row = 0
    )

select
    _dbt_source_relation,
    yearid,
    academic_year,
    region,
    schoolid,
    school_level,
    studentid,
    students_dcid,
    student_number,
    student_course_entry_date,
    grade_level,
    teacher_name,
    course_number,
    ap_course,
    section_or_period,
    sectionid,
    sections_dcid,
    assign_semester_code,
    assign_quarter,
    assign_category_code,
    assign_category,
    assign_category_quarter,
    assign_id,
    assign_name,
    assign_due_date,
    assign_score_type,
    assign_is_exempt,
    assign_is_late,
    assign_is_missing,
    assign_score_raw,
    assign_score_converted,
    assign_final_score_percent,
    assign_null_score,
    assign_scored,
    assign_expected_with_score,
    assign_expected_to_be_scored,
    assign_max_score,
    audit_yr_week_number,
    audit_qt_week_number,
    audit_start_date,
    audit_end_date,
    audit_due_date,

    if(assign_score_converted > assign_max_score, 1, 0) as assign_score_above_max,

    if(
        assign_is_exempt = 1 and assign_score_converted > 0, 1, 0
    ) as assign_exempt_with_score,

    if(
        assign_category_code = 'W' and assign_score_converted < 5, 1, 0
    ) as assign_w_score_less_5,

    if(
        assign_category_code = 'F' and assign_score_converted < 5, 1, 0
    ) as assign_f_score_less_5,

    if(
        assign_is_missing = 1
        and assign_category_code = 'W'
        and assign_score_converted != 5,
        1,
        0
    ) as assign_w_missing_score_not_5,

    if(
        assign_is_missing = 1
        and assign_category_code = 'F'
        and assign_score_converted != 5,
        1,
        0
    ) as assign_f_missing_score_not_5,

    if(
        assign_category_code = 'S' and assign_score_converted < (assign_max_score / 2),
        1,
        0
    ) as assign_s_score_less_50p,

    if(
        assign_is_exempt = 0
        and grade_level between 5 and 8
        and assign_category_code = 'S'
        and (assign_final_score_percent * 100)
        not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 90, 95, 100),
        1,
        0
    ) as assign_s_ms_score_not_conversion_chart_options,

    if(
        assign_is_exempt = 0
        and grade_level between 9 and 12
        and assign_category_code = 'S'
        and ap_course = 0
        and (assign_final_score_percent * 100)
        not in (50, 55, 58, 60, 65, 68, 70, 75, 78, 80, 85, 88, 93, 97, 100),
        1,
        0
    ) as assign_s_hs_score_not_conversion_chart_options,
from assign_2
