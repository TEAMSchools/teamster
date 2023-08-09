/* K-12 enrollments */
select
    ce.cc_dateenrolled,
    ce.cc_dateleft,
    ce.courses_credittype,
    ce.cc_academic_year + 1 as illuminate_academic_year,

    co.grade_level + 1 as illuminate_grade_level_id,

    ns.illuminate_subject_area,
    ns.is_foundations,

    ils.student_id as illuminate_student_id,

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
    {{ source("assessments", "src_assessments__course_subject_crosswalk") }} as ns
    on ce.cc_course_number = ns.powerschool_course_number
inner join
    {{ ref("stg_illuminate__students") }} as ils
    on co.student_number = ils.local_student_id
where not ce.is_dropped_course

union all

/* ES Writing */
select
    co.entrydate as cc_dateenrolled,
    co.exitdate as cc_dateleft,

    'RHET' as courses_credittype,

    co.academic_year + 1 as illuminate_academic_year,
    co.grade_level + 1 as illuminate_grade_level_id,

    'Writing' as illuminate_subject_area,
    false as is_foundations,

    ils.student_id as illuminate_student_id,

    false as is_advanced_math,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("stg_illuminate__students") }} as ils
    on co.student_number = ils.local_student_id
where co.code_location in ('kippnewark', 'kippcamden') and co.grade_level <= 4
