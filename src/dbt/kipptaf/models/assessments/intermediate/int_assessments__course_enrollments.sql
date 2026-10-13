with
    course_enrollments as (
        select
            students_student_number,
            cc_schoolid,
            cc_dateenrolled,
            cc_dcid,
            cc_course_number,
            cc_academic_year,
            is_foundations,
            _dbt_source_project,

            -- Focus leaves cc_dateleft null on open sections; exit_date is the
            -- term end there and equals cc_dateleft on PowerSchool rows
            exit_date as cc_dateleft,

            coalesce(discipline, core_subject) as discipline,

            -- Focus carries no advanced-math flag; null would drop its rows from
            -- the scaffold's `not is_advanced_math_student` gate
            coalesce(is_advanced_math, false) as is_advanced_math,

            -- Focus has no credit type; its homerooms are flagged by title only
            coalesce(
                courses_credittype, if(is_homeroom, 'HR', null)
            ) as courses_credittype,

            -- TODO(#5750): the crosswalk gives Focus courses only core_subject.
            -- int_assessments__resolved_section_enrollments keeps the reverse
            -- map (state subject to discipline) under TODO(#5715)
            coalesce(
                illuminate_subject_area,
                case
                    core_subject
                    when 'ELA'
                    then 'Text Study'
                    when 'Math'
                    then 'Mathematics'
                end
            ) as illuminate_subject_area,
        from {{ ref("int_students__course_enrollments") }}
        where not is_dropped_course
    ),

    enrollments_union as (
        /* K-12 enrollments */
        select
            ce.students_student_number as powerschool_student_number,
            ce.courses_credittype,
            ce.cc_schoolid as powerschool_school_id,
            ce.cc_dateenrolled,
            ce.cc_dateleft,
            ce.illuminate_subject_area,
            ce.discipline,
            ce.is_foundations,
            ce.cc_dcid,
            ce._dbt_source_project,

            co.region,

            ce.cc_academic_year + 1 as illuminate_academic_year,

            co.grade_level + 1 as illuminate_grade_level_id,

            -- no-subject rows (homeroom, PE, electives) dedupe per course, not
            -- into one row per enrollment date
            coalesce(
                ce.illuminate_subject_area, ce.cc_course_number
            ) as subject_or_course_key,

            -- Partitioned on `students_student_number`, not `cc_studentid`:
            -- Focus leaves `cc_studentid` null on every Miami row, so a
            -- partition on it collapses all Miami rows into 1 group. The 2 keys
            -- are exactly 1:1 within every NJ region — verified against prod,
            -- where distinct `cc_studentid`, distinct `students_student_number`
            -- and distinct pairs all match — so NJ output does not move.
            max(ce.is_advanced_math) over (
                partition by
                    ce._dbt_source_project,
                    ce.students_student_number,
                    ce.cc_academic_year,
                    ce.courses_credittype
            ) as is_advanced_math_student,
        from course_enrollments as ce
        -- cc_studentid is null on every Focus row, and #4972 moved Miami's
        -- student enrollments wholesale onto Focus for every year back to
        -- AY2018 -- so this join dropped all 93,858 Miami rows, archive years
        -- included, not just AY2026. student_number carries both SIS branches.
        --
        -- Deliberately NOT keyed on schoolid, unlike the (student_number,
        -- schoolid, academic_year) join in dim_student_section_enrollments:
        -- this join never carried schoolid, and adding it drops NJ rows where a
        -- student's course school differs from their enrollment school --
        -- Newark -2,271, Camden -389, Paterson -63, measured against prod. The
        -- student-key swap on its own is exactly NJ-neutral.
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on ce.students_student_number = co.student_number
            and ce.cc_academic_year = co.academic_year
            and ce._dbt_source_project = co._dbt_source_project
            and co.rn_year = 1

        union all

        /* ES Writing */
        select
            co.student_number as powerschool_student_number,

            'RHET' as courses_credittype,

            co.schoolid as powerschool_school_id,
            co.entrydate as cc_dateenrolled,
            co.exitdate as cc_dateleft,

            'Writing' as illuminate_subject_area,
            'ELA' as discipline,
            false as is_foundations,

            cast(null as int64) as cc_dcid,

            co._dbt_source_project,
            co.region,

            co.academic_year + 1 as illuminate_academic_year,
            co.grade_level + 1 as illuminate_grade_level_id,

            'Writing' as subject_or_course_key,

            false as is_advanced_math_student,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        where co.region in ('Newark', 'Camden') and co.grade_level <= 4
    )

    {{
        dbt_utils.deduplicate(
            relation="enrollments_union",
            partition_by="_dbt_source_project, powerschool_student_number, illuminate_academic_year, subject_or_course_key, cc_dateenrolled",
            order_by="cc_dateleft desc, cc_dcid desc",
        )
    }}
