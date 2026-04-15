with
    -- TODO: DISTINCT needed because upstream has multiple assessment_ids
    -- for the same logical assessment definition.
    illuminate_assessments as (
        select distinct
            'illuminate' as assessment_type,

            title,
            subject_area,
            scope,
            module_code,
            module_type,
            grade_level,
            is_internal_assessment,

            'enrollment' as assessment_scope,
        from {{ ref("int_assessments__assessments") }}
        where is_internal_assessment
    ),

    -- TODO: DISTINCT needed because upstream has per-student rows; no
    -- single dedup key exists at the assessment-definition grain.
    state_nj as (
        select distinct
            'state' as assessment_type,

            assessment_name as title,

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as subject_area,

            discipline as scope,

            case
                testcode
                when 'SC05'
                then 'SCI05'
                when 'SC08'
                then 'SCI08'
                when 'SC11'
                then 'SCI11'
                else testcode
            end as module_code,

            cast(null as string) as module_type,

            test_grade as grade_level,

            false as is_internal_assessment,

            'enrollment' as assessment_scope,
        from {{ ref("int_pearson__all_assessments") }}
        where testscalescore is not null
    ),

    -- TODO: DISTINCT needed because upstream has per-student rows.
    state_fl as (
        select distinct
            'state' as assessment_type,

            assessment_name as title,
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,

            cast(null as string) as module_type,

            cast(assessment_grade as int) as grade_level,

            false as is_internal_assessment,

            'enrollment' as assessment_scope,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    -- TODO: DISTINCT needed because upstream has per-student rows.
    college_assessments as (
        select distinct
            'college' as assessment_type,

            scope as title,
            subject_area,
            scope,
            score_type as module_code,

            cast(null as string) as module_type,
            cast(null as int64) as grade_level,

            false as is_internal_assessment,

            'student' as assessment_scope,
        from {{ ref("int_assessments__college_assessment") }}
    ),

    -- TODO: DISTINCT needed because upstream has per-student rows.
    ap_assessments as (
        select distinct
            'college' as assessment_type,

            concat('AP ', test_subject) as title,
            test_subject as subject_area,
            'AP' as scope,
            ps_ap_course_subject_code as module_code,

            cast(null as string) as module_type,
            cast(null as int64) as grade_level,

            false as is_internal_assessment,

            'student' as assessment_scope,
        from {{ ref("int_assessments__ap_assessments") }}
    ),

    all_assessments as (
        select *,
        from illuminate_assessments
        union all
        select *,
        from state_nj
        union all
        select *,
        from state_fl
        union all
        select *,
        from college_assessments
        union all
        select *,
        from ap_assessments
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level",
            ]
        )
    }} as assessment_key,

    assessment_type,
    title,
    subject_area,
    scope,
    module_code,
    module_type,
    grade_level as grade_level_tested,
    is_internal_assessment,
    assessment_scope,
from all_assessments
