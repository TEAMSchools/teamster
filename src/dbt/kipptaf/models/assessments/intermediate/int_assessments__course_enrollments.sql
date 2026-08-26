with
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

            -- partitioned on students_student_number rather than cc_studentid:
            -- Focus leaves cc_studentid null on every Miami row, so a partition
            -- on it collapses all Miami rows into a single group. The two keys
            -- are exactly 1:1 within every NJ region (verified against prod:
            -- distinct cc_studentid = distinct students_student_number =
            -- distinct pairs, in all three), so NJ output does not move.
            max(ce.is_advanced_math) over (
                partition by
                    ce._dbt_source_project,
                    ce.students_student_number,
                    ce.cc_academic_year,
                    ce.courses_credittype
            ) as is_advanced_math_student,
        from {{ ref("base_powerschool__course_enrollments") }} as ce
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
        -- TODO(#4996): is_dropped_course is null on every Focus row and
        -- `not null` is null, so this still removes Miami AY2026 even with the
        -- join above repointed. Miami's archive years carry real flags and do
        -- flow through. #4996 owns the coalesce decision for this filter.
        where not ce.is_dropped_course

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

            false as is_advanced_math_student,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        where co.region in ('Newark', 'Camden') and co.grade_level <= 4
    )

    {{
        dbt_utils.deduplicate(
            relation="enrollments_union",
            partition_by="_dbt_source_project, powerschool_student_number, illuminate_academic_year, illuminate_subject_area, cc_dateenrolled",
            order_by="cc_dateleft desc",
        )
    }}
