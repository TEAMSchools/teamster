with
    assign_1 as (
        select
            co._dbt_source_relation,
            co.cc_sectionid as sectionid,
            co.sections_dcid,
            co.cc_section_number as section_number,
            co.cc_course_number as course_number,
            co.teacher_lastfirst as teacher_name,
            co.cc_dateenrolled as student_course_entry_date,

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

            aud.yr_week_number as audit_yr_week_number,
            aud.qt_week_number as audit_qt_week_number,
            aud.start_date as audit_start_date,
            aud.end_date as audit_end_date,
            aud.due_date as audit_due_date,

            1 as counter,

            coalesce(s.islate, 0) as assign_is_late,
            coalesce(s.isexempt, 0) as assign_is_exempt,
            coalesce(s.ismissing, 0) as assign_is_missing,

            concat('Q', right(gb.storecode, 1)) as assign_quarter,

            concat(
                enr.region, enr.school_level, left(gb.storecode, 1)
            ) as es_exclude_concat,

            concat(
                enr.region, enr.school_level, gb.category_name
            ) as other_excluded_categories_concat,

            if(
                concat('Q', right(gb.storecode, 1)) in ('Q1', 'Q2'), 'S1', 'S2'
            ) as assign_semester_code,
            left(gb.storecode, 1) as assign_category_code,

            case
                when enr.school_level in ('ES', 'MS')
                then co.cc_section_number
                when enr.school_level = 'HS'
                then co.sections_external_expression
            end as `section`,

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
            and a.duedate between aud.start_date and aud.end_date
        where
            co.cc_academic_year = {{ var("current_academic_year") }}
            and not co.is_dropped_section
            and co.cc_dateleft >= current_date('America/New_York')
            and enr.enroll_status = 0
            and enr.school_level != 'OD'
            and a.iscountedinfinalgrade = 1
            and a.duedate between co.cc_dateenrolled and co.cc_dateleft
            and a.scoretype in ('POINTS', 'PERCENT')
            and gb.storecode not in ('Q1', 'Q2', 'Q3', 'Q4')
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
            student_course_entry_date,
            teacher_name,
            course_number,
            `section`,
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
        where
            assign_category_code != 'H'
            and es_exclude_concat
            not in ('NewarkESF', 'NewarkESS', 'CamdenESF', 'CamdenESS')
            and other_excluded_categories_concat not in (
                'NewarkHSParticipation',
                'CamdenHSParticipation',
                'NewarkHSMastery',
                'CamdenHSMastery'
            )
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
    student_course_entry_date,
    teacher_name,
    course_number,
    `section`,
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

    if(
        assign_id is not null and assign_score_converted > assign_max_score, 1, 0
    ) as assign_score_above_max,

    if(
        assign_is_exempt = 1
        and assign_score_converted > 0
        and assign_score_converted is not null,
        1,
        0
    ) as assign_exempt_with_score,

    if(
        assign_category_code = 'W'
        and assign_score_converted is not null
        and assign_score_converted < 5,
        1,
        0
    ) as assign_w_score_less_5,

    if(
        assign_category_code = 'F'
        and assign_score_converted is not null
        and assign_score_converted < 5,
        1,
        0
    ) as assign_f_score_less_5,

    if(
        assign_is_missing = 1
        and assign_category_code = 'W'
        and assign_score_converted is not null
        and assign_score_converted != 5,
        1,
        0
    ) as assign_w_missing_score_not_5,

    if(
        assign_is_missing = 1
        and assign_category_code = 'F'
        and assign_score_converted is not null
        and assign_score_converted != 5,
        1,
        0
    ) as assign_f_missing_score_not_5,

    if(
        assign_score_converted < (assign_max_score / 2), 1, 0
    ) as assign_s_score_less_50p,

from assign_2
