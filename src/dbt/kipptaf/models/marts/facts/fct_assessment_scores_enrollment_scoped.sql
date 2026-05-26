with
    -- Per `src/dbt/CLAUDE.md` hash-derivation rule: fact must re-join
    -- int_assessments__assessments to read raw `academic_year`, since
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
            rr.assessment_ids,
            rr.percent_correct,

            cast(rr.date_taken as date) as test_date,
            cast(a.administered_at as date) as administered_date,

            rr.assessment_id as source_assessment_id,
            a.academic_year,
            a.module_code,

            concat('kipp', lower(rr.region)) as _dbt_source_project,

            cast(null as numeric) as scale_score,

            rr.performance_band_label as proficiency_level,

            'internal' as score_source,
        from {{ ref("int_assessments__response_rollup") }} as rr
        left join
            {{ ref("int_assessments__assessments") }} as a
            on rr.assessment_id = a.assessment_id
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

    state_union as (
        select
            nj.student_number,
            nj.state_student_id,
            nj.academic_year,
            nj.subject_area,
            nj.discipline,
            nj.module_code,
            nj.grade_level,
            nj.scale_score,
            nj.is_proficient,
            nj.performance_band,
            nj.performance_band_level,
            nj.administration_period,
            nj.title,
            nj._dbt_source_project,
            nj.test_date,
            nj.percent_correct,
            nj.score_source,
            nj.assessment_type,
        from state_nj as nj

        union all

        select
            fl.student_number,
            fl.state_student_id,
            fl.academic_year,
            fl.subject_area,
            fl.discipline,
            fl.module_code,
            fl.grade_level,
            fl.scale_score,
            fl.is_proficient,
            fl.performance_band,
            fl.performance_band_level,
            fl.administration_period,
            fl.title,
            fl._dbt_source_project,
            fl.test_date,
            fl.percent_correct,
            fl.score_source,
            fl.assessment_type,
        from state_fl as fl
    )

/* internal assessments */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ia.student_number",
                "ia.assessment_id",
                "TO_JSON_STRING(ia.assessment_ids)",
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
                "cast(null as string)",
                "ia.source_assessment_id",
                "cast(null as string)",
            ]
        )
    }} as assessment_administration_key,

    {{ dbt_utils.generate_surrogate_key(["ia.student_number"]) }} as student_key,

    ia.test_date as test_date_key,

    ia.scale_score,
    ia.percent_correct,
    ia.proficiency_level,
    ia.is_mastery,
from internal_assessments as ia

union all

/* state assessments */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "su._dbt_source_project",
                "coalesce(cast(su.student_number as string), su.state_student_id)",
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
                "cast(null as date)",
                "su.academic_year",
                "su._dbt_source_project",
                "su.administration_period",
                "cast(null as int64)",
                "cast(null as string)",
            ]
        )
    }} as assessment_administration_key,

    if(
        ds.lea_student_identifier is not null,
        {{ dbt_utils.generate_surrogate_key(["su.student_number"]) }},
        cast(null as string)
    ) as student_key,

    su.test_date as test_date_key,

    su.scale_score,
    su.percent_correct,
    su.performance_band as proficiency_level,

    su.is_proficient as is_mastery,
from state_union as su
left join
    {{ ref("dim_students") }} as ds on su.student_number = ds.lea_student_identifier
