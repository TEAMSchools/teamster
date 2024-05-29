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

            aud.year_week_number,
            aud.quarter_week_number,
            aud.audit_start_date,
            aud.audit_end_date,
            aud.audit_due_date,

            gb.storecode as assign_category_quarter,
            gb.category_name as assign_category,
            gb.storecode_type as assign_category_code,

            a.scoretype as assign_score_type,
            a.assignmentid as assign_id,
            a.duedate as assign_due_date,
            a.name as assign_name,
            a.totalpointvalue as assign_max_score,

            s.scorepoints as assign_score_raw,

            concat('Q', gb.storecode_sequence) as assign_quarter,

            coalesce(s.islate, 0) as assign_is_late,
            coalesce(s.isexempt, 0) as assign_is_exempt,
            coalesce(s.ismissing, 0) as assign_is_missing,

            concat(
                enr.region, enr.school_level, gb.storecode_type
            ) as es_exclude_concat,
            concat(
                enr.region, enr.school_level, gb.category_name
            ) as other_excluded_categories_concat,

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

            case
                when enr.school_level in ('ES', 'MS')
                then co.cc_section_number
                when enr.school_level = 'HS'
                then co.sections_external_expression
            end as `section`,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        inner join
            {{ ref("base_powerschool__course_enrollments") }} as co
            on enr.studentid = co.cc_studentid
            and enr.yearid = co.cc_yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
            and not co.is_dropped_section
            and co.cc_dateleft >= current_date('America/New_York')
        inner join
            {{ ref("stg_reporting__gradebook_expectations") }} as aud
            on enr.academic_year = aud.academic_year
            and enr.region = aud.region
        inner join
            {{ ref("int_powerschool__section_grade_config") }} as gb
            on co.sections_dcid = gb.sections_dcid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="gb") }}
            and gb.grading_formula_weighting_type = 'Category_Weighting'
            and gb.storecode_type != 'H'
            and gb.storecode not in ('Q1', 'Q2', 'Q3', 'Q4')
        left join
            {{ ref("int_powerschool__gradebook_assignments") }} as a
            on gb.sections_dcid = a.sectionsdcid
            and gb.category_id = a.category_id
            and {{ union_dataset_join_clause(left_alias="gb", right_alias="a") }}
            and a.duedate between aud.audit_start_date and aud.audit_end_date
            and a.duedate between gb.term_start_date and gb.term_end_date
            and a.duedate between co.cc_dateenrolled and co.cc_dateleft
            and a.iscountedinfinalgrade = 1
            and a.scoretype in ('POINTS', 'PERCENT')
        left join
            {{ ref("int_powerschool__gradebook_assignment_scores") }} as s
            on a.assignmentsectionid = s.assignmentsectionid
            and enr.students_dcid = s.studentsdcid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
        where
            enr.academic_year = {{ var("current_academic_year") }}
            and enr.rn_year = 1
            and enr.enroll_status = 0
            and enr.school_level != 'OD'
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
            year_week_number,
            quarter_week_number,
            audit_start_date,
            audit_end_date,
            audit_due_date,

            safe_divide(
                assign_score_converted, assign_max_score
            ) as assign_final_score_percent,

            if(
                concat('Q', assign_quarter) in ('Q1', 'Q2'), 'S1', 'S2'
            ) as assign_semester_code,
        from assign_1
        where
            es_exclude_concat
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
    year_week_number,
    quarter_week_number,
    audit_start_date,
    audit_end_date,
    audit_due_date,

    1 as `counter`,

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
