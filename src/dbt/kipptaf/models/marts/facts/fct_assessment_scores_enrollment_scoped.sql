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
            rr.performance_band_label,
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

            cast(null as date) as test_date,
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

            cast(null as date) as test_date,
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

    {{ dbt_utils.generate_surrogate_key(["ia.student_number"]) }} as student_key,

    sr.student_section_enrollment_key,

    ia.test_date as test_date_key,

    ia.scale_score,
    ia.percent_correct,
    ia.proficiency_level,
    ia.is_mastery,
from internal_assessments as ia
-- ia.assessment_id is canonical-grain: int_assessments__response_rollup aliases
-- canonical_assessment_id as assessment_id, so it matches the resolver's
-- canonical_assessment_id join key.
left join
    {{ ref("int_assessments__resolved_section_enrollments") }} as sr
    on ia.student_number = sr.powerschool_student_number
    and ia.assessment_id = sr.canonical_assessment_id
    and ia._dbt_source_project = sr._dbt_source_project

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

    if(
        ds.lea_student_identifier is not null,
        {{ dbt_utils.generate_surrogate_key(["su.student_number"]) }},
        cast(null as string)
    ) as student_key,

    cast(null as string) as student_section_enrollment_key,

    su.test_date as test_date_key,

    su.scale_score,
    su.percent_correct,
    su.performance_band as proficiency_level,

    su.is_proficient as is_mastery,
from state_union as su
left join
    {{ ref("dim_students") }} as ds on su.student_number = ds.lea_student_identifier
