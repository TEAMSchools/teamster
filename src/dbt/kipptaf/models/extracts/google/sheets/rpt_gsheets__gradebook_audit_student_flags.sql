with
    quarter_course_grades as (
        select
            _dbt_source_project,
            academic_year,
            studentid,
            sectionid,
            storecode,
            term_percent_grade_adjusted as quarter_course_percent_grade,
            comment_value as quarter_comment_value,

            'current_year' as grades_type,

        from {{ ref("base_powerschool__final_grades") }}

        union all

        select
            _dbt_source_project,
            academic_year,
            studentid,
            sectionid,
            storecode,
            `percent` as quarter_course_percent_grade,
            comment_value as quarter_comment_value,

            'last_year' as grades_type,

        from {{ ref("stg_powerschool__storedgrades") }}
        where
            academic_year = {{ var("current_academic_year") - 1 }}
            and storecode_type = 'Q'
            and not is_transfer_grade
    ),

    student_course_flags as (
        select
            s._dbt_source_project,
            s.academic_year,
            s.academic_year_display,
            s.region,
            s.school_level_alt as school_level,
            s.schoolid,
            s.school,

            s.students_dcid,
            s.studentid,
            s.student_number,
            s.student_name,
            s.grade_level,

            s.sectionid,
            s.sections_dcid,
            s.course_number,
            s.course_name,
            s.section_number,
            s.external_expression,
            s.section_or_period,

            s.teacher_number,
            s.teacher_name,
            s.teacher_employee_number,

            s.`quarter`,
            s.semester,
            s.quarter_start_date,
            s.quarter_end_date,

            qg.quarter_course_percent_grade,
            qg.quarter_comment_value,

            if(
                qg.quarter_course_percent_grade > 100, true, false
            ) as qt_percent_grade_greater_100,

            if(
                qg.quarter_course_percent_grade < 70
                and qg.quarter_comment_value is null,
                true,
                false
            ) as qt_grade_70_comment_missing,

        from {{ ref("int_extracts__course_enrollments_by_term") }} as s
        inner join
            {{ ref("int_extracts__course_schedule_by_term") }} as sc
            on s._dbt_source_project = sc._dbt_source_project
            and s.sectionid = sc.sectionid
            and s.`quarter` = sc.`quarter`
            and s.academic_year = sc.academic_year
        left join
            quarter_course_grades as qg
            on s.academic_year = qg.academic_year
            and s.studentid = qg.studentid
            and s.sectionid = qg.sectionid
            and s._dbt_source_project = qg._dbt_source_project
            and s.`quarter` = qg.storecode
            and qg.grades_type = 'last_year'  /* summer toggle: see skill */
        where
            s.academic_year = {{ var("current_academic_year") - 1 }}  /* summer toggle: see skill */
            and s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
            and s.rn_year = 1
            and s.enroll_status = 0
            and s.school_level_alt != 'ES'
            and s._dbt_source_project != 'kippmiami'
            and not s.is_out_of_district
            and s.exclude_from_gpa = 0
    )

select
    _dbt_source_project,
    academic_year,
    academic_year_display,
    region,
    school_level,
    schoolid,
    school,

    students_dcid,
    studentid,
    student_number,
    student_name,
    grade_level,

    sectionid,
    sections_dcid,
    course_number,
    course_name,
    section_number,
    external_expression,
    section_or_period,

    teacher_number,
    teacher_name,
    teacher_employee_number,

    `quarter`,
    semester,
    quarter_start_date,
    quarter_end_date,

    quarter_course_percent_grade,
    quarter_comment_value,

    qt_percent_grade_greater_100,
    qt_grade_70_comment_missing,

from student_course_flags
where qt_percent_grade_greater_100 or qt_grade_70_comment_missing
