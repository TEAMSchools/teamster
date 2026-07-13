with
    -- Per `src/dbt/CLAUDE.md` hash-derivation rule: fact must re-join
    -- int_assessments__assessments_members to read raw `academic_year`, since
    -- response_rollup propagates `academic_year_clean as academic_year`
    -- (+1 offset) while dim_assessment_administrations hashes the raw value.
    internal_assessments as (
        select
            rr.powerschool_student_number as student_number,
            rr.assessment_id,
            rr.response_type,
            rr.response_type_id,
            rr.response_type_code,
            rr.response_type_description,
            rr.response_type_root_description,
            rr.is_replacement,
            rr.performance_band_label,
            rr.performance_band_label_number,
            rr.is_mastery,
            rr.n_assessments,
            rr.percent_correct,
            rr._dbt_source_project,

            rr.date_taken as test_date,

            to_json_string(rr.assessment_ids) as assessment_ids_json,

            rr.assessment_id as source_assessment_id,

            a.academic_year,
            a.module_code,

            c.administered_date,

            cast(null as numeric) as scale_score,

            rr.performance_band_label as proficiency_level,

            'internal' as score_source,
        from {{ ref("int_assessments__response_rollup") }} as rr
        inner join
            {{ ref("int_assessments__assessments_members") }} as a
            on rr.assessment_id = a.assessment_id
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on a.canonical_assessment_id = c.canonical_assessment_id
        where rr.is_internal_assessment
    ),

    state_nj as (
        select
            localstudentidentifier as student_number,
            academic_year,
            subject_area,
            illuminate_subject,
            discipline,
            module_code,
            administration_period,
            assessment_type,
            _dbt_source_project,

            cast(null as string) as state_student_id,

            test_grade as grade_level,
            testscalescore as scale_score,
            is_proficient,
            testperformancelevel_text as performance_band,
            testperformancelevel as performance_band_level,

            assessment_name as title,

            test_date,
            cast(null as numeric) as percent_correct,

            'state_nj' as score_source,
        from {{ ref("int_pearson__all_assessments") }}
        where
            academic_year >= {{ var("current_academic_year") - 7 }}
            and testscalescore is not null
    ),

    state_fl as (
        select
            student_number,
            academic_year,
            assessment_subject as subject_area,
            illuminate_subject,
            discipline,
            test_code as module_code,
            scale_score,
            is_proficient,
            administration_window as administration_period,
            assessment_type,
            _dbt_source_project,

            student_id as state_student_id,

            achievement_level as performance_band,
            performance_level as performance_band_level,

            assessment_name as title,

            cast(assessment_grade as int) as grade_level,

            test_date,
            cast(null as numeric) as percent_correct,

            'state_fl' as score_source,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    state_all as (
        select
            student_number,
            state_student_id,
            academic_year,
            subject_area,
            illuminate_subject,
            discipline,
            module_code,
            grade_level,
            scale_score,
            is_proficient,
            performance_band,
            performance_band_level,
            administration_period,
            title,
            _dbt_source_project,
            test_date,
            percent_correct,
            score_source,
            assessment_type,
        from state_nj

        union all

        select
            student_number,
            state_student_id,
            academic_year,
            subject_area,
            illuminate_subject,
            discipline,
            module_code,
            grade_level,
            scale_score,
            is_proficient,
            performance_band,
            performance_band_level,
            administration_period,
            title,
            _dbt_source_project,
            test_date,
            percent_correct,
            score_source,
            assessment_type,
        from state_fl
    ),

    state_union as (
        select
            sa.*,

            coalesce(
                cast(sa.student_number as string), sa.state_student_id
            ) as student_identifier,
        from state_all as sa
    ),

    iready_scores_raw as (
        select
            student_id as student_number,
            academic_year_int as academic_year,
            subject as module_code,
            illuminate_subject,
            test_round as administration_period,
            completion_date as test_date,
            `start_date`,
            _dbt_source_project,

            overall_relative_placement as proficiency_level,

            'iready' as score_source,

            cast(overall_scale_score as numeric) as scale_score,
            cast(percentile as numeric) as growth_percentile,

            overall_relative_placement_int >= 4 as is_mastery,
        from {{ ref("int_iready__diagnostic_results") }}
        where overall_scale_score is not null
    ),

    -- TODO(#4387): stg_iready__diagnostic_results has no uniqueness test;
    -- same-day retests and duplicate rows exist upstream. Remove this dedupe
    -- when staging is fixed.
    iready_scores as (
        {{
            dbt_utils.deduplicate(
                relation="iready_scores_raw",
                partition_by="""
                    _dbt_source_project,
                    student_number,
                    academic_year,
                    administration_period,
                    module_code,
                    test_date
                """,
                order_by="start_date desc, scale_score desc",
            )
        }}
    ),

    star_scores_raw as (
        select
            student_display_id as student_number,
            academic_year,
            star_subject as module_code,
            illuminate_subject,
            screening_period_window_name as administration_period,
            completed_date_value as test_date,
            assessment_id,
            _dbt_source_project,

            state_benchmark_category_name as proficiency_level,

            'star' as score_source,

            cast(unified_score as numeric) as scale_score,
            cast(percentile_rank as numeric) as growth_percentile,

            state_benchmark_proficient = 'Yes' as is_mastery,
        from {{ ref("stg_renlearn__star") }}
        where
            completed_date_value is not null
            and unified_score is not null
            and _dbt_source_project is not null
    ),

    -- TODO(#4388): stg_renlearn__star holds fiscal-year re-pull duplicates
    -- (same assessment_id in two partitions) and same-day retests. Remove
    -- this dedupe when staging is fixed.
    star_scores as (
        {{
            dbt_utils.deduplicate(
                relation="star_scores_raw",
                partition_by="""
                    _dbt_source_project,
                    student_number,
                    academic_year,
                    administration_period,
                    module_code,
                    test_date
                """,
                order_by="scale_score desc, assessment_id desc",
            )
        }}
    ),

    -- DIBELS benchmark composites are unique at this grain upstream
    -- (verified); no dedupe needed.
    dibels_scores as (
        select
            student_number,
            academic_year,
            measure_standard as module_code,
            illuminate_subject,
            `period` as administration_period,
            client_date as test_date,
            _dbt_source_project,

            measure_standard_level as proficiency_level,

            'dibels' as score_source,

            cast(measure_standard_score as numeric) as scale_score,
            cast(measure_percentile as numeric) as growth_percentile,

            measure_standard_level_int >= 3 as is_mastery,
        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark' and measure_standard = 'Composite'
    ),

    vendor_all as (
        select
            student_number,
            academic_year,
            module_code,
            illuminate_subject,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            growth_percentile,
            is_mastery,
        from iready_scores

        union all

        select
            student_number,
            academic_year,
            module_code,
            illuminate_subject,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            growth_percentile,
            is_mastery,
        from star_scores

        union all

        select
            student_number,
            academic_year,
            module_code,
            illuminate_subject,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            growth_percentile,
            is_mastery,
        from dibels_scores
    )

/* internal assessments */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ia.student_number",
                "ia.assessment_id",
                "ia.assessment_ids_json",
                "ia.response_type",
                "ia.response_type_id",
                "ia.response_type_code",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "ia.module_code",
                "ia.administered_date",
                "ia.academic_year",
                "ia._dbt_source_project",
                "null",
                "ia.source_assessment_id",
                "null",
            ]
        )
    }} as assessment_administration_key,

    sr.student_section_enrollment_key,

    ia.test_date as test_date_key,

    ia.scale_score,
    ia.percent_correct,

    cast(null as numeric) as growth_percentile,

    ia.proficiency_level,
    ia.is_mastery,
    ia.response_type,
    ia.response_type_code,
    ia.response_type_description,
    ia.response_type_root_description,
    ia.is_replacement,
    ia.performance_band_label_number,

    sr.resolution_type as enrollment_resolution,
from internal_assessments as ia
-- ia.assessment_id is canonical-grain: int_assessments__response_rollup aliases
-- canonical_assessment_id as assessment_id, so it matches the resolver's
-- canonical_assessment_id join key. INNER drops internal scores with no
-- resolved section (out of scope) -- the resolver is the scope of record.
inner join
    {{ ref("int_assessments__resolved_section_enrollments") }} as sr
    on ia.student_number = sr.powerschool_student_number
    and ia.assessment_id = sr.canonical_assessment_id
    and ia._dbt_source_project = sr._dbt_source_project
    and sr.source_type = 'internal'

union all

/* state assessments */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "su._dbt_source_project",
                "su.student_identifier",
                "su.academic_year",
                "su.administration_period",
                "su.subject_area",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "su.assessment_type",
                "su.module_code",
                "null",
                "su.academic_year",
                "su._dbt_source_project",
                "su.administration_period",
                "null",
                "null",
            ]
        )
    }} as assessment_administration_key,

    sr.student_section_enrollment_key,

    su.test_date as test_date_key,

    su.scale_score,
    su.percent_correct,

    cast(null as numeric) as growth_percentile,

    su.performance_band as proficiency_level,
    su.is_proficient as is_mastery,

    cast(null as string) as response_type,
    cast(null as string) as response_type_code,
    cast(null as string) as response_type_description,
    cast(null as string) as response_type_root_description,
    cast(null as bool) as is_replacement,
    cast(null as numeric) as performance_band_label_number,

    sr.resolution_type as enrollment_resolution,
from state_union as su
-- the resolver keys state scores on illuminate_subject (the state->course
-- subject mapping), not the raw subject_area the assessment_score_key hashes.
-- join on su.illuminate_subject = sr.subject_area or every row drops.
-- INNER scopes the fact to state scores with a resolved section.
inner join
    {{ ref("int_assessments__resolved_section_enrollments") }} as sr
    on su.student_number = sr.powerschool_student_number
    and su.academic_year = sr.academic_year
    and su.administration_period = sr.administration_period
    and su.illuminate_subject = sr.subject_area
    and su._dbt_source_project = sr._dbt_source_project
    and sr.source_type in ('state_nj', 'state_fl')

union all

/* vendor assessments (iReady, STAR, DIBELS) */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "va.score_source",
                "va._dbt_source_project",
                "va.student_number",
                "va.academic_year",
                "va.administration_period",
                "va.module_code",
                "va.test_date",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "va.score_source",
                "va.module_code",
                "null",
                "va.academic_year",
                "va._dbt_source_project",
                "va.administration_period",
                "null",
                "null",
            ]
        )
    }} as assessment_administration_key,

    sr.student_section_enrollment_key,

    va.test_date as test_date_key,

    va.scale_score,

    cast(null as numeric) as percent_correct,

    va.growth_percentile,
    va.proficiency_level,
    va.is_mastery,

    cast(null as string) as response_type,
    cast(null as string) as response_type_code,
    cast(null as string) as response_type_description,
    cast(null as string) as response_type_root_description,
    cast(null as bool) as is_replacement,
    cast(null as numeric) as performance_band_label_number,

    sr.resolution_type as enrollment_resolution,
from vendor_all as va
-- the resolver keys vendor scores on illuminate_subject (the vendor->course
-- subject mapping), not the raw vendor subject the assessment_score_key
-- hashes. INNER scopes the fact to vendor scores with a resolved section.
inner join
    {{ ref("int_assessments__resolved_section_enrollments") }} as sr
    on va.student_number = sr.powerschool_student_number
    and va.academic_year = sr.academic_year
    and va.administration_period = sr.administration_period
    and va.illuminate_subject = sr.subject_area
    and va._dbt_source_project = sr._dbt_source_project
    and va.score_source = sr.source_type
