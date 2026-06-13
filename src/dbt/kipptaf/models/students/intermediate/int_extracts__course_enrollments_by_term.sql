with
    schedule_by_terms as (
        select
            e._dbt_source_project,
            e.cc_academic_year,
            e.cc_schoolid,
            e.cc_studentid,
            e.cc_sectionid as sectionid,
            e.cc_course_number as course_number,
            e.sections_dcid,
            e.sections_section_number as section_number,
            e.sections_external_expression as external_expression,
            e.courses_credittype as credit_type,
            e.courses_course_name as course_name,
            e.courses_excludefromgpa as exclude_from_gpa,
            e.sections_no_of_students,
            e.teachernumber as teacher_number,
            e.teacher_lastfirst as teacher_name,

            t.term as `quarter`,
            t.term_start_date as quarter_start_date,
            t.term_end_date as quarter_end_date,
            t.is_current_term as is_current_quarter,

            row_number() over (
                partition by e.cc_studentid, e.cc_course_number, t.term
                order by e.cc_dateleft desc
            ) as rn,

        from {{ ref("base_powerschool__course_enrollments") }} as e
        inner join
            {{ ref("int_powerschool__terms") }} as t
            on e.cc_academic_year = t.academic_year
            and e.cc_schoolid = t.schoolid
            and e._dbt_source_project = t._dbt_source_project
            and e.cc_dateenrolled <= t.term_end_date
            and e.cc_dateleft >= t.term_start_date
        where
            e.cc_academic_year = {{ var("current_academic_year") }}
            and not e.is_dropped_section
    ),

    -- one school enrollment row per student per year; prefer latest exitdate
    student_enrollment as (
        select
            *,

            row_number() over (
                partition by _dbt_source_project, studentid, academic_year
                order by exitdate desc
            ) as rn,

        from {{ ref("int_extracts__student_enrollments") }}
        where exitdate >= date(academic_year, 8, 1)
        qualify rn = 1
    )

select
    e.*,

    s.sectionid,
    s.course_number,
    s.sections_dcid,
    s.section_number,
    s.external_expression,
    s.credit_type,
    s.course_name,
    s.exclude_from_gpa,
    s.sections_no_of_students,
    s.teacher_number,
    s.teacher_name,
    s.`quarter`,
    s.quarter_start_date,
    s.quarter_end_date,
    s.is_current_quarter,

from student_enrollment as e
inner join
    schedule_by_terms as s
    on e.academic_year = s.cc_academic_year
    and e.schoolid = s.cc_schoolid
    and e.studentid = s.cc_studentid
    and e._dbt_source_project = s._dbt_source_project
    and s.rn = 1
