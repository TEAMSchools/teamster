with
    asmts as (
        select
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year,
            a.academic_year_clean,
            a.scope,
            a.subject_area,

            ias.module_type,

            regexp_replace(
                coalesce(
                    regexp_extract(a.title, ias.module_number_pattern_1 || r'\s?\d+'),
                    regexp_extract(a.title, ias.module_number_pattern_2 || r'\s?\d+')
                ),
                r'\s',
                ''
            ) as module_number,
        from {{ ref("base_illuminate__assessments") }} as a
        inner join
            {{ source("assessments", "src_assessments__internal_assessment_scopes") }}
            as ias
            on a.scope = ias.scope
            and a.academic_year_clean = ias.academic_year
    ),

    assessments_union as (
        /* K-8 */
        select
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean,
            a.module_type,
            a.module_number,
            a.scope,
            a.subject_area,

            agl.grade_level_id,

            ssa.student_id,

            false as is_replacement,
        from asmts as a
        inner join
            {{ ref("stg_illuminate__assessment_grade_levels") }} as agl
            on a.assessment_id = agl.assessment_id
        inner join
            {{ ref("base_illuminate__student_session_aff") }} as ssa
            on a.academic_year = ssa.academic_year
            and agl.grade_level_id = ssa.grade_level_id
            and ssa.rn_student_session_desc = 1
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on ssa.student_id = ce.illuminate_student_id
            and a.subject_area = ce.illuminate_subject_area
            and a.administered_at between ce.cc_dateenrolled and ce.cc_dateleft
            and not ce.is_advanced_math_student
        where
            agl.grade_level_id <= 9
            and a.subject_area
            in ('Text Study', 'Mathematics', 'Social Studies', 'Science')

        union all

        /* HS */
        select
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean,
            a.module_type,
            a.module_number,
            a.scope,
            a.subject_area,

            agl.grade_level_id,

            ce.illuminate_student_id as student_id,

            false as is_replacement,
        from asmts as a
        inner join
            {{ ref("stg_illuminate__assessment_grade_levels") }} as agl
            on a.assessment_id = agl.assessment_id
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on agl.grade_level_id = ce.illuminate_grade_level_id
            and a.subject_area = ce.illuminate_subject_area
            and a.administered_at between ce.cc_dateenrolled and ce.cc_dateleft
        where
            agl.grade_level_id >= 10
            and a.subject_area
            not in ('Text Study', 'Mathematics', 'Social Studies', 'Science')

        union all

        /* replacement curriculum */
        select  -- distinct
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean,
            a.module_type,
            a.module_number,
            a.scope,
            a.subject_area,

            null as grade_level_id,

            sa.student_id,

            true as is_replacement,
        from asmts as a
        inner join
            {{ ref("stg_illuminate__students_assessments") }} as sa
            on a.assessment_id = sa.assessment_id
        inner join
            {{ ref("base_illuminate__student_session_aff") }} as ssa
            on a.academic_year = ssa.academic_year
            and sa.student_id = ssa.student_id
            and ssa.rn_student_session_desc = 1
            and ssa.grade_level_id <= 9
        left join
            {{ ref("stg_illuminate__assessment_grade_levels") }} as agl
            on a.assessment_id = agl.assessment_id
            and ssa.grade_level_id = agl.grade_level_id
        where
            a.subject_area in ('Text Study', 'Mathematics', 'Social Studies', 'Science')
            and agl.assessment_grade_level_id is null
    )

select
    assessment_id,
    title,
    administered_at,
    performance_band_set_id,
    academic_year_clean as academic_year,
    subject_area,
    grade_level_id,
    student_id,
    is_replacement,
    if(
        scope in ('Cumulative Review Quizzes', 'Cold Read Quizzes')
        and grade_level_id in (1, 2),
        'Checkpoint',
        scope
    ) as scope,
    if(
        scope in ('Cumulative Review Quizzes', 'Cold Read Quizzes')
        and grade_level_id in (1, 2),
        'CP',
        module_type
    ) as module_type,
    if(
        scope in ('Cumulative Review Quizzes', 'Cold Read Quizzes')
        and grade_level_id in (1, 2),
        replace(module_number, 'CRQ', 'CP'),
        module_number
    ) as module_number,
from assessments_union
