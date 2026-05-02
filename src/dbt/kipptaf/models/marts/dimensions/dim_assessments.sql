with
    -- DISTINCT projects from response grain (one row per student) to
    -- definition grain (one row per assessment definition). Per-student
    -- columns are not in the projection, so byte-identical projected tuples
    -- are coalesced. Not a workaround for dirty data — the projection IS
    -- the operation. Per-administration attributes live on
    -- dim_assessment_administrations.
    -- Member-grain: one row per actual Illuminate assessment_id. Bridge
    -- table `bridge_assessment_administration_members` maps each
    -- canonical-grain `dim_assessment_administrations` row to its member(s)
    -- via this dim's `assessment_key`.
    illuminate_assessments as (
        select
            assessment_id as source_assessment_id,
            title,
            subject_area,
            scope,
            module_code,
            module_type,
            grade_level,
            is_internal_assessment,

            'illuminate' as assessment_type,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_assessments__assessments") }}
        where is_internal_assessment
    ),

    -- DISTINCT projects from response grain to definition grain (see
    -- illuminate_assessments comment above).
    state_nj as (
        select distinct
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

            test_grade as grade_level,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,

            'state' as assessment_type,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_pearson__all_assessments") }}
        where testscalescore is not null
    ),

    -- DISTINCT projects from response grain to definition grain (see
    -- illuminate_assessments comment above).
    state_fl as (
        select distinct
            assessment_name as title,
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,

            cast(assessment_grade as int) as grade_level,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,

            'state' as assessment_type,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    -- DISTINCT projects from response grain to definition grain (see
    -- illuminate_assessments comment above).
    college_assessments as (
        select distinct
            scope as title,
            subject_area,
            scope,
            score_type as module_code,

            aligned_subject as combined_academic_subject,
            aligned_subject_area as aligned_academic_subject,
            course_discipline as credit_category,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as int64) as grade_level,

            'college' as assessment_type,
            false as is_internal_assessment,
            'student' as assessment_scope,

            'Official' as test_type,
        from {{ ref("int_assessments__college_assessment") }}
    ),

    -- DISTINCT projects from response grain to definition grain. Practice
    -- college tests (mock SAT/ACT) administered through Illuminate.
    practice_assessments as (
        select distinct
            scope as title,
            subject_area,
            scope,
            scope as module_code,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as int64) as grade_level,

            'college' as assessment_type,
            false as is_internal_assessment,
            'student' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,

            'Practice' as test_type,
        from {{ ref("int_assessments__college_assessment_practice") }}
    ),

    -- DISTINCT projects from response grain to definition grain (see
    -- illuminate_assessments comment above).
    ap_assessments as (
        select distinct
            concat('AP ', test_subject) as title,
            test_subject as subject_area,
            ps_ap_course_subject_code as module_code,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as int64) as grade_level,

            'ap' as assessment_type,
            'AP' as scope,
            false as is_internal_assessment,
            'student' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_assessments__ap_assessments") }}
    ),

    {%- set union_cols -%}
    assessment_type, source_assessment_id, title, subject_area, scope,
    module_code, module_type, grade_level, is_internal_assessment,
    assessment_scope, combined_academic_subject, aligned_academic_subject,
    credit_category, test_type
    {%- endset -%}

    all_assessments as (
        select {{ union_cols }},
        from illuminate_assessments
        union all
        select {{ union_cols }},
        from state_nj
        union all
        select {{ union_cols }},
        from state_fl
        union all
        select {{ union_cols }},
        from college_assessments
        union all
        select {{ union_cols }},
        from practice_assessments
        union all
        select {{ union_cols }},
        from ap_assessments
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "module_code",
                "source_assessment_id",
                "test_type",
            ]
        )
    }} as assessment_key,

    title,
    module_code,
    module_type,
    is_internal_assessment,
    combined_academic_subject,
    aligned_academic_subject,
    credit_category,
    source_assessment_id,
    test_type,

    assessment_type as `type`,
    subject_area as academic_subject,
    scope as category,
    grade_level as grade_level_tested,
    assessment_scope as scope,
from all_assessments
