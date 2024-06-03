with
    assign_1 as (
        select
            co._dbt_source_relation,
            co.cc_sectionid as sectionid,
            co.sections_dcid,
            co.cc_section_number as section_number,
            co.cc_course_number as course_number,
            co.teacher_lastfirst as teacher_name,

            enr.academic_year,
            enr.student_number,
            enr.studentid,
            enr.students_dcid,
            enr.yearid,
            enr.region,
            enr.schoolid,
            enr.grade_level,
            enr.school_level,

            gb.storecode as assign_category_quarter,
            gb.category_name as assign_category,

            a.scoretype as assign_score_type,
            a.assignmentid as assign_id,
            a.duedate as assign_due_date,
            a.name as assign_name,
            a.totalpointvalue as assign_max_score,

            s.scorepoints as assign_score_raw,

            aud.year_week_number as audit_yr_week_number,
            aud.quarter_week_number as audit_qt_week_number,
            aud.audit_start_date,
            aud.audit_end_date,
            aud.audit_due_date,

            1 as counter,

            coalesce(s.islate, 0) as assign_is_late,
            coalesce(s.isexempt, 0) as assign_is_exempt,
            coalesce(s.ismissing, 0) as assign_is_missing,

            concat('Q', right(gb.storecode, 1)) as assign_quarter,

            if(
                enr.grade_level <= 4,
                co.cc_section_number,
                co.sections_external_expression
            ) as section_or_period,

            if(
                enr.grade_level > 4 or (enr.grade_level <= 4 and enr.region = 'Miami'),
                0,
                1
            ) as exclude_row,

            if(
                concat('Q', right(gb.storecode, 1)) in ('Q1', 'Q2'), 'S1', 'S2'
            ) as assign_semester_code,
            left(gb.storecode, 1) as assign_category_code,

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

        from {{ ref("base_powerschool__course_enrollments") }} as co
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as enr
            on co.cc_studentid = enr.studentid
            and co.cc_yearid = enr.yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
            and enr.rn_year = 1
        inner join
            {{ ref("int_powerschool__section_grade_config") }} as gb
            on co.sections_dcid = gb.sections_dcid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="gb") }}
            and gb.grading_formula_weighting_type != 'Total_Points'
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on gb.sections_dcid = a.sectionsdcid
            and gb.category_id = a.category_id
            and a.duedate between gb.term_start_date and gb.term_end_date
            and {{ union_dataset_join_clause(left_alias="gb", right_alias="a") }}
        left join
            {{ ref("int_powerschool__gradebook_assignment_scores") }} as s
            on a.assignmentsectionid = s.assignmentsectionid
            and enr.students_dcid = s.studentsdcid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
        left join
            {{ ref("stg_reporting__gradebook_expectations") }} as aud
            on enr.academic_year = aud.academic_year
            and enr.region = aud.region
            and a.duedate between aud.audit_start_date and aud.audit_end_date
        where
            co.cc_academic_year = {{ var("current_academic_year") }}
            and co.cc_course_number != 'HR'
            and not co.is_dropped_section
            and co.cc_dateleft >= current_date('America/New_York')
            and enr.enroll_status = 0
            and enr.school_level != 'OD'
            and a.iscountedinfinalgrade = 1
            and a.duedate between co.cc_dateenrolled and co.cc_dateleft
            and a.scoretype in ('POINTS', 'PERCENT')
            and left(gb.storecode, 1) not in ('Q', 'H')
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
            grade_level,
            teacher_name,
            course_number,
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
            counter,

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
    grade_level,
    teacher_name,
    course_number,
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
    counter,

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
        assign_score_converted < (assign_max_score / 2), 1, 0
    ) as assign_s_score_less_50p,

from assign_2
