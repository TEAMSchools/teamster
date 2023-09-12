{{ config(materialized="table") }}

with
    assessments as (
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
            if(ias.module_type is not null, true, false) as is_internal_assessment,

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

    internal_assessments as (
        {# /* K-8 */ #}
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
            a.is_internal_assessment,

            agl.grade_level_id,

            ssa.student_id as illuminate_student_id,

            s.local_student_id as powerschool_student_number,

            ce.powerschool_school_id,

            false as is_replacement,
        from assessments as a
        inner join
            {{ ref("stg_illuminate__assessment_grade_levels") }} as agl
            on a.assessment_id = agl.assessment_id
        inner join
            {{ ref("base_illuminate__student_session_aff") }} as ssa
            on a.academic_year = ssa.academic_year
            and agl.grade_level_id = ssa.grade_level_id
            and ssa.rn_student_session_desc = 1
        inner join
            {{ ref("stg_illuminate__students") }} as s on ssa.student_id = s.student_id
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on a.subject_area = ce.illuminate_subject_area
            and a.administered_at between ce.cc_dateenrolled and ce.cc_dateleft
            and s.local_student_id = ce.powerschool_student_number
            and not ce.is_advanced_math_student
        where
            a.is_internal_assessment
            and a.subject_area
            in ('Text Study', 'Mathematics', 'Social Studies', 'Science')
            and agl.grade_level_id <= 9

        union all

        {# /* HS */#}
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
            a.is_internal_assessment,

            agl.grade_level_id,

            s.student_id as illuminate_student_id,

            ce.powerschool_student_number,
            ce.powerschool_school_id,

            false as is_replacement,
        from assessments as a
        inner join
            {{ ref("stg_illuminate__assessment_grade_levels") }} as agl
            on a.assessment_id = agl.assessment_id
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on agl.grade_level_id = ce.illuminate_grade_level_id
            and a.subject_area = ce.illuminate_subject_area
            and a.administered_at between ce.cc_dateenrolled and ce.cc_dateleft
        inner join
            {{ ref("stg_illuminate__students") }} as s
            on ce.powerschool_student_number = s.local_student_id
        where
            a.is_internal_assessment
            and a.subject_area
            not in ('Text Study', 'Mathematics', 'Social Studies', 'Science')
            and agl.grade_level_id >= 10
    )

select
    ia.illuminate_student_id,
    ia.powerschool_student_number,
    ia.assessment_id,
    ia.title,
    ia.subject_area,
    ia.academic_year_clean as academic_year,
    ia.administered_at,
    ia.performance_band_set_id,
    ia.powerschool_school_id,
    ia.grade_level_id,
    ia.is_internal_assessment,
    ia.is_replacement,
    if(
        ia.scope in ('Cumulative Review Quizzes', 'Cold Read Quizzes')
        and ia.grade_level_id in (1, 2),
        'Checkpoint',
        ia.scope
    ) as scope,
    if(
        ia.scope in ('Cumulative Review Quizzes', 'Cold Read Quizzes')
        and ia.grade_level_id in (1, 2),
        'CP',
        ia.module_type
    ) as module_type,
    if(
        ia.scope in ('Cumulative Review Quizzes', 'Cold Read Quizzes')
        and ia.grade_level_id in (1, 2),
        replace(module_number, 'CRQ', 'CP'),
        ia.module_number
    ) as module_number,

    sa.student_assessment_id,
    sa.date_taken,
from internal_assessments as ia
left join
    {{ ref("stg_illuminate__students_assessments") }} as sa
    on ia.illuminate_student_id = sa.student_id
    and ia.assessment_id = sa.assessment_id

union all

{# /* K-8 replacement curriculum */ #}
select
    sa.student_id as illuminate_student_id,

    s.local_student_id as powerschool_student_number,

    a.assessment_id,
    a.title,
    a.subject_area,
    a.academic_year_clean as academic_year,
    a.administered_at,
    a.performance_band_set_id,

    ssa.site_id as powerschool_school_id,

    null as grade_level_id,

    a.is_internal_assessment,

    true as is_replacement,

    a.scope,
    a.module_type,
    a.module_number,

    sa.student_assessment_id,
    sa.date_taken,
from assessments as a
inner join
    {{ ref("stg_illuminate__students_assessments") }} as sa
    on a.assessment_id = sa.assessment_id
inner join {{ ref("stg_illuminate__students") }} as s on sa.student_id = s.student_id
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
    a.is_internal_assessment
    and a.subject_area in ('Text Study', 'Mathematics', 'Social Studies', 'Science')
    and agl.assessment_grade_level_id is null

union all

{# all other assessments #}
select
    sa.student_id as illuminate_student_id,

    s.local_student_id as powerschool_student_number,

    a.assessment_id,
    a.title,
    a.subject_area,
    a.academic_year_clean as academic_year,
    a.administered_at,
    a.performance_band_set_id,

    ssa.site_id as powerschool_school_id,

    null as grade_level_id,

    a.is_internal_assessment,

    false as is_replacement,

    a.scope,
    a.module_type,
    a.module_number,

    sa.student_assessment_id,
    sa.date_taken,
from assessments as a
inner join
    {{ ref("stg_illuminate__students_assessments") }} as sa
    on a.assessment_id = sa.assessment_id
inner join {{ ref("stg_illuminate__students") }} as s on sa.student_id = s.student_id
inner join
    {{ ref("base_illuminate__student_session_aff") }} as ssa
    on a.academic_year = ssa.academic_year
    and sa.student_id = ssa.student_id
    and ssa.rn_student_session_desc = 1
where not a.is_internal_assessment
