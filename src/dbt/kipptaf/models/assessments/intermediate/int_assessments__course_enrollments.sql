{{ config(materialized="table") }}

with
    enrollments_union as (
        /* K-12 enrollments */
        select
            ce.cc_dateenrolled,
            ce.cc_dateleft,
            ce.courses_credittype,
            ce.cc_academic_year + 1 as illuminate_academic_year,

            co.student_number as powerschool_student_number,
            co.schoolid as powerschool_school_id,
            co.grade_level + 1 as illuminate_grade_level_id,

            ns.illuminate_subject_area,
            ns.is_foundations,

            max(ns.is_advanced_math) over (
                partition by ce.cc_studentid, ce.cc_academic_year, ce.courses_credittype
            ) as is_advanced_math_student,
        from {{ ref("base_powerschool__course_enrollments") }} as ce
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on ce.cc_studentid = co.studentid
            and ce.cc_academic_year = co.academic_year
            and {{ union_dataset_join_clause(left_alias="ce", right_alias="co") }}
            and co.rn_year = 1
        inner join
            {{ source("assessments", "src_assessments__course_subject_crosswalk") }}
            as ns
            on ce.cc_course_number = ns.powerschool_course_number
        where not ce.is_dropped_course

        union all

        /* ES Writing */
        select
            co.entrydate as cc_dateenrolled,
            co.exitdate as cc_dateleft,

            'RHET' as courses_credittype,

            co.academic_year + 1 as illuminate_academic_year,
            co.student_number as powerschool_student_number,
            co.schoolid as powerschool_school_id,
            co.grade_level + 1 as illuminate_grade_level_id,

            'Writing' as illuminate_subject_area,
            false as is_foundations,
            false as is_advanced_math,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        where co.code_location in ('kippnewark', 'kippcamden') and co.grade_level <= 4
    )

    {{
        dbt_utils.deduplicate(
            relation="enrollments_union",
            partition_by="powerschool_student_number, illuminate_academic_year, illuminate_subject_area",
            order_by="cc_dateenrolled desc, cc_dateleft desc",
        )
    }}
