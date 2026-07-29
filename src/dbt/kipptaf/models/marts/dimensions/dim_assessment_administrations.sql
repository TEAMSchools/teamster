with
    illuminate_administrations as (
        select
            subject_area,
            scope,
            module_code,
            academic_year,
            administered_date,
            grade_level,

            title,

            'illuminate' as assessment_type,

            canonical_assessment_id as source_assessment_id,

            cast(null as string) as administration_period,
            cast(null as string) as test_type,

            concat('kipp', lower(region)) as _dbt_source_project,
        from {{ ref("int_assessments__assessments_canonical") }}
        cross join unnest(regions_array) as region
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- State NJ PARCC: one administration per (testcode, period, academic_year,
    -- _dbt_source_project).
    state_nj_parcc_administrations as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,
            academic_year,
            administration_period,
            _dbt_source_project,

            'state_nj_parcc' as assessment_type,
            'PARCC' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("stg_pearson__parcc") }}
        where testscalescore is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- State NJ NJSLA: one administration per (testcode, period, academic_year,
    -- _dbt_source_project).
    state_nj_njsla_administrations as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,
            academic_year,
            administration_period,
            _dbt_source_project,

            'state_nj_njsla' as assessment_type,
            'NJSLA' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("stg_pearson__njsla") }}
        where testscalescore is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- State NJ NJSLA Science: one administration per (testcode, period,
    -- academic_year, _dbt_source_project).
    state_nj_njsla_science_administrations as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,
            academic_year,
            administration_period,
            _dbt_source_project,

            'state_nj_njsla_science' as assessment_type,
            'NJSLA Science' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("stg_pearson__njsla_science") }}
        where testscalescore is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- State NJ NJGPA: one administration per (testcode, period, academic_year,
    -- _dbt_source_project).
    state_nj_njgpa_administrations as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,
            academic_year,
            administration_period,
            _dbt_source_project,

            'state_nj_njgpa' as assessment_type,
            'NJGPA' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("stg_pearson__njgpa") }}
        where testscalescore is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- State FL FAST: one administration per (test_code, administration_window,
    -- academic_year).
    state_fl_fast_administrations as (
        select distinct
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,
            grade_level,
            academic_year,
            administration_window as administration_period,
            _dbt_source_project,

            'state_fl_fast' as assessment_type,
            'FAST' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("stg_fldoe__fast") }}
        where scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- State FL FSA: one administration per (test_code, administration_window,
    -- academic_year).
    state_fl_fsa_administrations as (
        select distinct
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,
            grade_level,
            academic_year,
            administration_window as administration_period,
            _dbt_source_project,

            'state_fl_fsa' as assessment_type,
            'FSA' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("stg_fldoe__fsa") }}
        where scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- State FL EOC: one administration per (test_code, administration_window,
    -- academic_year).
    state_fl_eoc_administrations as (
        select distinct
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,
            grade_level,
            academic_year,
            administration_window as administration_period,
            _dbt_source_project,

            'state_fl_eoc' as assessment_type,
            'EOC' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("stg_fldoe__eoc") }}
        where scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- State FL Science: one administration per (test_code, administration_window,
    -- academic_year).
    state_fl_science_administrations as (
        select distinct
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,
            grade_level,
            academic_year,
            administration_window as administration_period,
            _dbt_source_project,

            'state_fl_science' as assessment_type,
            'Science' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("stg_fldoe__science") }}
        where scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- iReady: one administration per (subject, test_round, academic_year,
    -- _dbt_source_project).
    iready_administrations as (
        select distinct
            subject as subject_area,
            subject as module_code,
            academic_year_int as academic_year,
            test_round as administration_period,
            _dbt_source_project,

            'iready' as assessment_type,
            'i-Ready Diagnostic' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,

            if(subject = 'Math', 'Math', 'ELA') as scope,
        from {{ ref("int_iready__diagnostic_results") }}
        where overall_scale_score is not null and _dbt_source_project is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- STAR: one administration per (star_subject, screening window,
    -- academic_year, _dbt_source_project).
    star_administrations as (
        select distinct
            star_subject as subject_area,
            star_subject as module_code,
            academic_year,
            screening_period_window_name as administration_period,
            _dbt_source_project,

            'star' as assessment_type,
            'STAR' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,

            if(star_subject = 'Math', 'Math', 'ELA') as scope,
        from {{ ref("stg_renlearn__star") }}
        where
            completed_date_value is not null
            and unified_score is not null
            and _dbt_source_project is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- DIBELS: one administration per (benchmark window, academic_year,
    -- _dbt_source_project); module_code is the Composite measure.
    dibels_administrations as (
        select distinct
            measure_standard as module_code,
            academic_year,
            `period` as administration_period,
            _dbt_source_project,

            'Reading' as subject_area,
            'dibels' as assessment_type,
            'DIBELS' as title,
            'ELA' as scope,

            cast(null as date) as administered_date,
            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark' and measure_standard = 'Composite'
    ),

    -- College Official: one administration per (score_type, test_date,
    -- administration_round). _dbt_source_project is null because college tests
    -- are region-agnostic.
    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    college_administrations as (
        select distinct
            scope,
            subject_area,
            score_type as module_code,
            test_date as administered_date,
            academic_year,
            administration_round as administration_period,

            'college' as assessment_type,
            scope as title,

            cast(null as int64) as grade_level,
            cast(null as string) as _dbt_source_project,
            cast(null as int64) as source_assessment_id,

            'Official' as test_type,
        from {{ ref("int_assessments__college_assessment") }}
    ),

    -- College Practice: one administration per (scope, test_date,
    -- administration_round). _dbt_source_project is null because college tests
    -- are region-agnostic. Aggregates across subject_area rows in the upstream
    -- model.
    practice_administrations as (
        select
            scope,
            academic_year,

            scope as title,
            scope as module_code,
            test_date as administered_date,
            administration_round as administration_period,

            'college' as assessment_type,
            'Practice' as test_type,

            cast(null as string) as _dbt_source_project,
            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,

            any_value(subject_area) as subject_area,
        from {{ ref("int_assessments__college_assessment_practice") }}
        group by scope, test_date, academic_year, administration_round
    ),

    -- AP: one administration per (subject, academic_year). Test date is
    -- not captured upstream.
    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    ap_administrations as (
        select distinct
            title,
            academic_year,

            test_subject as subject_area,
            ps_ap_course_subject_code as module_code,

            'ap' as assessment_type,
            'AP' as scope,

            cast(null as date) as administered_date,
            cast(null as int64) as grade_level,
            cast(null as string) as _dbt_source_project,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as administration_period,
            cast(null as string) as test_type,
        from {{ ref("int_assessments__ap_assessments") }}
    ),

    {%- set union_cols -%}
        assessment_type, title, subject_area, scope, module_code, grade_level,
        administered_date, academic_year, _dbt_source_project,
        source_assessment_id, administration_period, test_type
    {%- endset %}

    all_administrations as (
        select {{ union_cols }},
        from illuminate_administrations
        union all
        select {{ union_cols }},
        from state_nj_njgpa_administrations
        union all
        select {{ union_cols }},
        from state_nj_njsla_administrations
        union all
        select {{ union_cols }},
        from state_nj_njsla_science_administrations
        union all
        select {{ union_cols }},
        from state_nj_parcc_administrations
        union all
        select {{ union_cols }},
        from state_fl_eoc_administrations
        union all
        select {{ union_cols }},
        from state_fl_fast_administrations
        union all
        select {{ union_cols }},
        from state_fl_fsa_administrations
        union all
        select {{ union_cols }},
        from state_fl_science_administrations
        union all
        select {{ union_cols }},
        from iready_administrations
        union all
        select {{ union_cols }},
        from star_administrations
        union all
        select {{ union_cols }},
        from dibels_administrations
        union all
        select {{ union_cols }},
        from college_administrations
        union all
        select {{ union_cols }},
        from practice_administrations
        union all
        select {{ union_cols }},
        from ap_administrations
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "module_code",
                "administered_date",
                "academic_year",
                "_dbt_source_project",
                "administration_period",
                "source_assessment_id",
                "test_type",
            ]
        )
    }} as assessment_administration_key,

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

    -- `academic_year` is intentionally not exposed in the final SELECT —
    -- it's a hash input only. The canonical-grain dim represents an
    -- administration scoped by `_dbt_source_project` + `administered_date_key`
    -- + `administration_period`. Academic year is resolved downstream on
    -- `fct_assessment_scores_enrollment_scoped.assessment_date_key` via
    -- `dim_dates`, NOT on `administered_date_key` — which is null for state and
    -- vendor administrations, so deriving academic year from it there yields
    -- null (#4546).
    administered_date as administered_date_key,

    _dbt_source_project,
    administration_period,
    source_assessment_id,
    test_type,
from all_administrations
