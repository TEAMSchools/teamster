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
    -- Collapse historical title variants (NJSLA / PARCC share a module_code
    -- per grade) to one row per assessment_key hash input set. NJ kept
    -- distinct from FL via assessment_type='state_nj' (FL state tests share
    -- module_codes like ELA05/MAT05/SCI05 but are functionally different
    -- assessments).
    state_nj as (
        select
            discipline as scope,
            test_grade as grade_level,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,

            'state_nj' as assessment_type,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,

            aligned_subject as subject_area,

            aligned_test_code as module_code,

            min(assessment_name) as title,
        from {{ ref("int_pearson__all_assessments") }}
        where testscalescore is not null
        group by discipline, test_grade, `subject`, aligned_test_code, aligned_subject
    ),

    -- Collapse historical title variants (FAST / FSA share a test_code per
    -- grade) to one row per assessment_key hash input set. FL kept distinct
    -- from NJ via assessment_type='state_fl'.
    state_fl as (
        select
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,

            cast(assessment_grade as int) as grade_level,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,

            'state_fl' as assessment_type,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,

            min(assessment_name) as title,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
        group by assessment_subject, discipline, test_code, assessment_grade
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

    -- One row per (scope, subject_area) — matching Official college's
    -- per-subject grain (Official uses score_type as module_code, e.g.,
    -- 'sat_math'). Practice derives a parallel module_code by concatenating
    -- scope and subject_area so SAT Math, SAT Reading, etc. each get their
    -- own assessment_key.
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

    -- DISTINCT projects from response grain to definition grain (see
    -- illuminate_assessments comment above).
    ap_assessments as (
        select distinct
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

            concat('AP ', test_subject) as title,
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
