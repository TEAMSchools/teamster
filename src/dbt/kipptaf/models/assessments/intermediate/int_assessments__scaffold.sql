with
    asmts as (
        select
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean as academic_year,
            a.scope,
            a.subject_area,

            ias.module_type,
            if(ias.scope is not null, true, false) as is_internal_assessment,

            regexp_replace(
                coalesce(
                    regexp_extract(a.title, ias.module_number_pattern_1 || r'\s?\d+'),
                    regexp_extract(a.title, ias.module_number_pattern_2 || r'\s?\d+')
                ),
                r'\s',
                ''
            ) as module_number,
        from {{ ref("base_illuminate__assessments") }} as a
        left join
            {{ source("assessments", "src_assessments__internal_assessment_scopes") }}
            as ias
            on a.scope = ias.scope
            and a.academic_year_clean = ias.academic_year
    ),

    assessments_union as (
        /* K-8 subject areas */
        select
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean as academic_year,
            a.module_type,
            a.module_number,
            a.scope,
            a.subject_area,
            a.is_normed_scope,

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
            and ssa.rn = 1
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on ssa.student_id = ce.student_id
            and a.subject_area = ce.subject_area
            and a.administered_at between ce.entry_date and ce.leave_date
            and not ce.is_advanced_math_student
        where
            a.is_internal_assessment
            and a.subject_area
            in ('Text Study', 'Mathematics', 'Social Studies', 'Science')

        union all

        /* HS subject areas */
        select
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean as academic_year,
            a.module_type,
            a.module_number,
            a.scope,
            a.subject_area,
            a.is_normed_scope,

            agl.grade_level_id,

            ce.student_id,

            false as is_replacement,
        from asmts as a
        inner join
            {{ ref("stg_illuminate__assessment_grade_levels") }} as agl
            on a.assessment_id = agl.assessment_id
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on agl.grade_level_id = ce.grade_level_id
            and a.subject_area = ce.subject_area
            and a.administered_at between ce.entry_date and ce.leave_date
        where
            a.is_internal_assessment
            and a.subject_area
            not in ('Text Study', 'Mathematics', 'Social Studies', 'Science')

        union all

        /* replacement curriculum */
        select distinct
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean as academic_year,
            a.module_type,
            a.module_number,
            a.scope,
            a.subject_area,
            a.is_normed_scope,

            null as grade_level_id,

            sa.student_id,

            true as is_replacement,
        from asmts as a
        inner join
            {{ ref("stg_illuminate__assessment_grade_levels") }} as agl
            on a.assessment_id = agl.assessment_id
        inner join
            {{ ref("stg_illuminate__students_assessments") }} as sa
            on a.assessment_id = sa.assessment_id
        inner join
            {{ ref("base_illuminate__student_session_aff") }} as ssa
            on sa.student_id = ssa.student_id
            and a.academic_year = ssa.academic_year
            and agl.grade_level_id != ssa.grade_level_id
            and ssa.rn = 1
        where
            a.is_internal_assessment
            and a.subject_area
            in ('Text Study', 'Mathematics', 'Social Studies', 'Science')

        union all

        /* all other assessments */
        select
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean as academic_year,
            a.module_type,
            a.module_number,
            a.scope,
            a.subject_area,
            a.is_normed_scope,

            null as grade_level_id,

            sa.student_id,

            false as is_replacement,
        from asmts as a
        inner join
            {{ ref("stg_illuminate__students_assessments") }} as sa
            on a.assessment_id = sa.assessment_id
        where not a.is_internal_assessment
    )

select
    assessment_id,
    title,
    administered_at,
    performance_band_set_id,
    academic_year,
    subject_area,
    is_normed_scope,
    grade_level_id,
    student_id,
    is_replacement,
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
    if(
        scope in ('Cumulative Review Quizzes', 'Cold Read Quizzes')
        and grade_level_id in (1, 2),
        'Checkpoint',
        scope
    ) as scope,
from assessments_union
