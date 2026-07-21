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
    is_current_quarter,

    quarter_course_percent_grade,
    quarter_comment_value,

    qt_percent_grade_greater_100,
    qt_grade_70_comment_missing,

from {{ ref("int_extracts__gradebook_audit_student_flags") }}
where qt_percent_grade_greater_100 or qt_grade_70_comment_missing
