with
    schedule_by_terms as (
        select
            c._dbt_source_project,
            c.cc_academic_year,
            c.cc_schoolid as schoolid,
            c.cc_studentid,
            c.cc_sectionid as sectionid,
            c.cc_course_number as course_number,
            c.sections_dcid,
            c.sections_section_number as section_number,
            c.sections_external_expression as external_expression,
            c.courses_credittype as credit_type,
            c.courses_course_name as course_name,
            c.courses_excludefromgpa as exclude_from_gpa,
            c.teachernumber as teacher_number,
            c.teacher_lastfirst as teacher_name,

            t.term as `quarter`,
            t.term_start_date as quarter_start_date,
            t.term_end_date as quarter_end_date,
            t.is_current_term as is_current_quarter,

            date_diff(
                least(c.cc_dateleft, t.term_end_date),
                greatest(c.cc_dateenrolled, t.term_start_date),
                day
            )
            + 1 as days_enrolled_in_quarter,

            date_diff(t.term_end_date, t.term_start_date, day)
            + 1 as quarter_length_days,

        from {{ ref("base_powerschool__course_enrollments") }} as c
        inner join
            {{ ref("int_powerschool__terms") }} as t
            on c.cc_academic_year = t.academic_year
            and c.cc_schoolid = t.schoolid
            and c._dbt_source_project = t._dbt_source_project
            and c.cc_dateenrolled <= t.term_end_date
            and c.cc_dateleft >= t.term_start_date
        where
            c.cc_academic_year = {{ var("current_academic_year") }}
            and c.courses_credittype in ('HR', 'MATH', 'ENG')
            and not c.is_dropped_section
            and c.sections_no_of_students != 0
    )

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

    c.sectionid,
    c.course_number,
    c.sections_dcid,
    c.section_number,
    c.external_expression,
    c.credit_type,
    c.course_name,
    c.exclude_from_gpa,
    c.teacher_number,
    c.teacher_name,
    c.quarter,
    c.quarter_start_date,
    c.quarter_end_date,
    c.is_current_quarter,

    qg.comment_value,

    if(qg.comment_value is null, true, false) as qt_es_comment_missing,

    safe_divide(c.days_enrolled_in_quarter, c.quarter_length_days)
    < 0.25 as is_partial_quarter,

from {{ ref("int_extracts__student_enrollments") }} as s
inner join
    schedule_by_terms as c
    on s.studentid = c.cc_studentid
    and s.academic_year = c.cc_academic_year
    and s._dbt_source_project = c._dbt_source_project
left join
    {{ ref("base_powerschool__final_grades") }} as qg
    on c.cc_academic_year = qg.academic_year
    and c.cc_studentid = qg.studentid
    and c.sectionid = qg.sectionid
    and c._dbt_source_project = qg._dbt_source_project
    and c.quarter = qg.storecode
    and qg.termbin_start_date <= current_date('{{ var("local_timezone") }}')
where
    s.academic_year = {{ var("current_academic_year") }}
    and s.region != 'Miami'
    and s.school_level = 'ES'
    and s.rn_year = 1
    and s.enroll_status = 0
    and not s.is_out_of_district
