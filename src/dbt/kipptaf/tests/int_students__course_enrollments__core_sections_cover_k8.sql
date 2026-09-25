with
    -- grain projection, not dup-masking: one row per student per school-year,
    -- collapsing multiple enrollment stints at the same school
    k8_students as (
        select distinct
            academic_year, _dbt_source_project, region, schoolid, student_number,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and grade_level between 0 and 8
    ),

    expected as (
        select
            s.academic_year,
            s._dbt_source_project,
            s.region,
            s.schoolid,
            s.student_number,

            subject,
        from k8_students as s
        cross join unnest(['ELA', 'Math']) as subject
    ),

    core_sections as (
        select
            cc_academic_year,
            _dbt_source_project,
            cc_schoolid,
            students_student_number,
            core_subject,
        from {{ ref("int_students__course_enrollments") }}
        where rn_core_subject_year = 1
    ),

    coverage as (
        select
            e.region,
            e.subject,

            count(*) as n_students,
            countif(c.students_student_number is not null) as n_with_core_section,
            safe_divide(
                countif(c.students_student_number is not null), count(*)
            ) as coverage_rate,
        from expected as e
        left join
            core_sections as c
            on e.academic_year = c.cc_academic_year
            and e._dbt_source_project = c._dbt_source_project
            and e.schoolid = c.cc_schoolid
            and e.student_number = c.students_student_number
            and e.subject = c.core_subject
        group by e.region, e.subject
    )

select region, subject, n_students, n_with_core_section, coverage_rate,
from coverage
where coverage_rate < 0.95
