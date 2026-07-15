select
    s._dbt_source_project,
    s.academic_year,
    s.academic_year_display,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.students_dcid,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level,
    s.enroll_status,
    s.cohort,
    s.gender,
    s.ethnicity,
    s.advisory,
    s.hos,
    s.iep_status,
    s.lep_status,
    s.is_504,
    s.is_counseling_services,
    s.is_student_athlete,
    s.`ada`,
    s.ada_above_or_at_80,
    s.sectionid,
    s.course_number,
    s.sections_dcid,
    s.section_number,
    s.external_expression,
    s.credit_type,
    s.course_name,
    s.exclude_from_gpa,
    s.teacher_number,
    s.teacher_name,
    s.quarter,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

    qg.comment_value,

    if(qg.comment_value is null, true, false) as qt_es_comment_missing,

from {{ ref("int_extracts__course_enrollments_by_term") }} as s
left join
    {{ ref("base_powerschool__final_grades") }} as qg
    on s.academic_year = qg.academic_year
    and s.studentid = qg.studentid
    and s.sectionid = qg.sectionid
    and s._dbt_source_project = qg._dbt_source_project
    and s.`quarter` = qg.storecode
    and qg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
where
    s.academic_year = {{ var("current_academic_year") }}
    /* alt so Sumner G5 (treated as MS) stays in the audit, not the ES view */
    and s.region_school_level_alt in ('CamdenES', 'NewarkES', 'PatersonES')
    and s.credit_type in ('HR', 'MATH', 'ENG')
    and s.enroll_status = 0
    and not s.is_out_of_district
    and s.quarter_start_date <= current_date('{{ var("local_timezone") }}')
