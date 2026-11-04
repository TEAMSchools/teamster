with
    students as (
        select student_number, schoolid, grade_level, _dbt_source_project,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and not is_out_of_district
            and enroll_status in (0, -1)
            -- Miami rosters into Clever from Focus, not from this feed
            and _dbt_source_project != 'kippmiami'
    ),

    enrollments as (
        select
            ce.cc_schoolid as school_id,

            s.student_number as student_id,

            concat(ce._dbt_source_project, ce.cc_sectionid) as section_id,
        from {{ ref("int_students__course_enrollments") }} as ce
        inner join
            students as s
            on ce.students_student_number = s.student_number
            and ce._dbt_source_project = s._dbt_source_project
        where ce.exit_date >= current_date('{{ var("local_timezone") }}')

        union all

        select
            schoolid as school_id,
            student_number as student_id,

            concat(
                {{ var("current_academic_year") - 1990 }},
                schoolid,
                right(concat(0, grade_level), 2)
            ) as section_id,
        from students
    )

select school_id, section_id, student_id,
from enrollments
