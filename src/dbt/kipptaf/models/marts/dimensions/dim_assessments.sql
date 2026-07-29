with
    -- Member-grain: one row per actual Illuminate assessment_id. Bridge
    -- table `bridge_assessment_administration_members` maps each
    -- canonical-grain `dim_assessment_administrations` row to its member(s)
    -- via this dim's `assessment_key`.
    illuminate_assessments as (
        select
            m.assessment_id as source_assessment_id,
            m.title,
            m.subject_area,
            m.scope,
            m.module_code,
            m.module_type,
            m.is_internal_assessment,

            c.grade_level,

            'illuminate' as assessment_type,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_assessments__assessments_members") }} as m
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on m.canonical_assessment_id = c.canonical_assessment_id
        where m.is_internal_assessment
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    state_nj_parcc as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,

            'state_nj_parcc' as assessment_type,
            'PARCC' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("stg_pearson__parcc") }}
        where testscalescore is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    state_nj_njsla as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,

            'state_nj_njsla' as assessment_type,
            'NJSLA' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("stg_pearson__njsla") }}
        where testscalescore is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    state_nj_njsla_science as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,

            'state_nj_njsla_science' as assessment_type,
            'NJSLA Science' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("stg_pearson__njsla_science") }}
        where testscalescore is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    state_nj_njgpa as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,

            'state_nj_njgpa' as assessment_type,
            'NJGPA' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("stg_pearson__njgpa") }}
        where testscalescore is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    state_fl_fast as (
        select distinct
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,
            grade_level,

            'state_fl_fast' as assessment_type,
            'FAST' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("stg_fldoe__fast") }}
        where scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    state_fl_fsa as (
        select distinct
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,
            grade_level,

            'state_fl_fsa' as assessment_type,
            'FSA' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("stg_fldoe__fsa") }}
        where scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    state_fl_eoc as (
        select distinct
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,
            grade_level,

            'state_fl_eoc' as assessment_type,
            'EOC' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("stg_fldoe__eoc") }}
        where scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    state_fl_science as (
        select distinct
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,
            grade_level,

            'state_fl_science' as assessment_type,
            'Science' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("stg_fldoe__science") }}
        where scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    iready_assessments as (
        select distinct
            subject as subject_area,
            subject as module_code,

            'iready' as assessment_type,
            'i-Ready Diagnostic' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,

            if(subject = 'Math', 'Math', 'ELA') as scope,
        from {{ ref("int_iready__diagnostic_results") }}
        where overall_scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    star_assessments as (
        select distinct
            star_subject as subject_area,
            star_subject as module_code,

            'star' as assessment_type,
            'STAR' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,

            if(star_subject = 'Math', 'Math', 'ELA') as scope,
        from {{ ref("stg_renlearn__star") }}
        where completed_date_value is not null and unified_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    dibels_assessments as (
        select distinct
            measure_standard as module_code,

            'Reading' as subject_area,
            'dibels' as assessment_type,
            'DIBELS' as title,
            'ELA' as scope,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark' and measure_standard = 'Composite'
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
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

    -- One row per (scope, subject_area) — matching Official college's
    -- per-subject grain (Official uses score_type as module_code, e.g.,
    -- 'sat_math'). Practice derives a parallel module_code by concatenating
    -- scope and subject_area so SAT Math, SAT Reading, etc. each get their
    -- own assessment_key.
    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    practice_assessments as (
        select distinct
            scope,
            subject_area,

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

            scope as title,

            lower(concat(scope, '_', replace(subject_area, ' ', '_'))) as module_code,
        from {{ ref("int_assessments__college_assessment_practice") }}
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    ap_assessments as (
        select distinct
            title,
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
    {%- endset %}

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    all_assessments_unioned as (
        select {{ union_cols }},
        from illuminate_assessments
        union all
        select {{ union_cols }},
        from state_nj_njgpa
        union all
        select {{ union_cols }},
        from state_nj_njsla
        union all
        select {{ union_cols }},
        from state_nj_njsla_science
        union all
        select {{ union_cols }},
        from state_nj_parcc
        union all
        select {{ union_cols }},
        from state_fl_eoc
        union all
        select {{ union_cols }},
        from state_fl_fast
        union all
        select {{ union_cols }},
        from state_fl_fsa
        union all
        select {{ union_cols }},
        from state_fl_science
        union all
        select {{ union_cols }},
        from iready_assessments
        union all
        select {{ union_cols }},
        from star_assessments
        union all
        select {{ union_cols }},
        from dibels_assessments
        union all
        select {{ union_cols }},
        from college_assessments
        union all
        select {{ union_cols }},
        from practice_assessments
        union all
        select {{ union_cols }},
        from ap_assessments
    ),

    -- Dedup after union: state_nj and state_fl historically share module_codes
    -- (e.g., ELA06, SCI05) for the same logical grade-level state assessment.
    -- Per src/dbt/CLAUDE.md "Canonical attributes from a partition": pick all
    -- attributes from a single row (ordered by title for determinism) rather
    -- than independent min() calls that could draw from different rows.
    all_assessments as (
        {{
            dbt_utils.deduplicate(
                relation="all_assessments_unioned",
                partition_by="assessment_type, source_assessment_id, module_code, test_type",
                order_by="title",
            )
        }}
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
