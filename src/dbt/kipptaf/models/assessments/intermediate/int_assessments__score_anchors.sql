with
    -- internal scores anchor on the scheduled administration date. date_taken
    -- is occasionally corrupt (epoch / year-2000 sentinels) and anchoring on it
    -- dropped scores whose bad date missed every enrollment window (#4183).
    internal_anchored as (
        select
            sc.powerschool_student_number,
            sc.canonical_assessment_id,
            sc.subject_area,
            sc._dbt_source_project,

            c.administered_date as anchor_date,

            row_number() over (
                partition by
                    sc.powerschool_student_number,
                    sc.canonical_assessment_id,
                    sc._dbt_source_project
                order by c.administered_date asc
            ) as rn,
        from {{ ref("int_assessments__scaffold") }} as sc
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on sc.canonical_assessment_id = c.canonical_assessment_id
        where sc.is_internal_assessment and not sc.is_replacement
    ),

    internal_scores as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            subject_area,
            _dbt_source_project,
            anchor_date,

            cast(null as int64) as academic_year,
            cast(null as string) as administration_period,

            'internal' as source_type,
        from internal_anchored
        where rn = 1
    ),

    -- rows with no test date or no student cannot resolve -> dropped
    state_nj_scores as (
        select
            localstudentidentifier as powerschool_student_number,
            academic_year,
            administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            test_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'state_nj' as source_type,
        from {{ ref("int_pearson__all_assessments") }}
        where test_date is not null and localstudentidentifier is not null
    ),

    state_fl_scores as (
        select
            student_number as powerschool_student_number,
            academic_year,
            administration_window as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            test_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'state_fl' as source_type,
        from {{ ref("int_fldoe__all_assessments") }}
        where test_date is not null and student_number is not null
    ),

    iready_scores as (
        select
            student_id as powerschool_student_number,
            academic_year_int as academic_year,
            test_round as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            completion_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'iready' as source_type,
        from {{ ref("int_iready__diagnostic_results") }}
        where completion_date is not null and overall_scale_score is not null
    ),

    -- rows without a crosswalk-resolved project cannot join course
    -- enrollments and are dropped
    star_scores as (
        select
            student_display_id as powerschool_student_number,
            academic_year,
            screening_period_window_name as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            completed_date_value as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'star' as source_type,
        from {{ ref("stg_renlearn__star") }}
        where
            completed_date_value is not null
            and unified_score is not null
            and _dbt_source_project is not null
    ),

    -- benchmark composites only; PM probes and subskill measures are out of
    -- scope
    dibels_scores as (
        select
            student_number as powerschool_student_number,
            academic_year,
            `period` as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            client_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'dibels' as source_type,
        from {{ ref("int_amplify__all_assessments") }}
        where
            assessment_type = 'Benchmark'
            and measure_standard = 'Composite'
            and client_date is not null
    ),

    scores as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from internal_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from state_nj_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from state_fl_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from iready_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from star_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from dibels_scores
    ),

    scores_keyed as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "powerschool_student_number",
                        "_dbt_source_project",
                        "source_type",
                        "canonical_assessment_id",
                        "academic_year",
                        "administration_period",
                        "subject_area",
                    ]
                )
            }} as score_grain_key,
        from scores
    )

-- grain projection, not dup-masking: every projected column is in the grain
-- (score_grain_key inputs + anchor_date), so only byte-identical rows coalesce
select distinct
    powerschool_student_number,
    canonical_assessment_id,
    academic_year,
    administration_period,
    subject_area,
    _dbt_source_project,
    anchor_date,
    source_type,
    score_grain_key,
from scores_keyed
