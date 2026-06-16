with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    demographics_distinct as (
        select distinct
            student_number,
            academic_year,
            region,
            school,
            grade_level,
            iep_status,
            lep_status,
            status_504,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
    ),

    -- a student can hold more than one enrollment (school/grade) within a year
    -- (mid-year transfers); collapse to one row per student/year by a
    -- deterministic pick (highest grade_level, then school). For the small set of
    -- transfers this attributes the year's rows to a single school/grade.
    demographics as (
        {{
            dbt_utils.deduplicate(
                relation="demographics_distinct",
                partition_by="student_number, academic_year",
                order_by="grade_level desc, school",
            )
        }}
    ),

    courses as (
        select
            students_student_number as student_number,
            cc_academic_year as academic_year,
            courses_credittype as credittype,
            teachernumber as teacher_powerschool_teacher_number,
            cc_course_number as course_number,
            cc_section_number as section_number,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            rn_credittype_year = 1
            and not is_dropped_section
            and courses_credittype in ('ENG', 'MATH')
    )

select
    ru.student_number,
    ru.academic_year,
    ru.assessment_source,
    ru.`subject`,
    ru.administration_round,
    ru.assessment_id,
    ru.assessment_title,
    ru.scale_score,
    ru.percent_correct,
    ru.is_proficient,
    ru.performance_band_label,
    ru.performance_band_int,

    de.region,
    de.school as school_abbreviation,
    de.grade_level,
    de.iep_status,
    de.status_504,
    de.lep_status as ml_status,

    c.teacher_powerschool_teacher_number,
    c.course_number,
    c.section_number,
from {{ ref("int_assessments__roster_union") }} as ru
-- demographics is the enrollment gate: the grade 0-8 (K-8) scope is enforced
-- here, so this join is INNER. Assessment rows for a student with no
-- enrollment-subjects record for that year are intentionally dropped.
inner join
    demographics as de
    on ru.student_number = de.student_number
    and ru.academic_year = de.academic_year
left join
    courses as c
    on ru.student_number = c.student_number
    and ru.academic_year = c.academic_year
    and case when ru.`subject` = 'ELA' then 'ENG' else 'MATH' end = c.credittype
where de.grade_level between 0 and 8
