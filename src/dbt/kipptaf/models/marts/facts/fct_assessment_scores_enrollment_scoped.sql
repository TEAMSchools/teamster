with
    internal_assessments as (
        select
            rr.powerschool_student_number as student_number,
            rr.region,
            rr.assessment_id,
            rr.response_type,
            rr.response_type_id,
            rr.response_type_code,
            rr.performance_band_label,
            rr.is_mastery,
            rr.n_assessments,
            rr.assessment_ids,
            rr.percent_correct,

            a.title,
            a.subject_area,
            a.scope,
            a.module_code,
            a.grade_level,
            a.academic_year,

            cast(rr.date_taken as date) as test_date,
            cast(a.administered_at as date) as administered_date,

            cast(null as numeric) as scale_score,

            rr.performance_band_label as proficiency_level,

            cast(null as numeric) as growth_percentile,

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

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as subject_area,

            discipline,

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
            testscalescore as scale_score,
            is_proficient,
            testperformancelevel_text as performance_band,
            testperformancelevel as performance_band_level,

            if(`period` = 'FallBlock', 'Fall', `period`) as administration_window,

            if(`period` = 'FallBlock', 'Fall', `period`) as season,

            assessment_name as title,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            _dbt_source_relation,

            cast(null as date) as test_date,
            cast(null as numeric) as percent_correct,
            cast(null as numeric) as growth_percentile,

            'state_nj' as score_source,
        from {{ ref("int_pearson__all_assessments") }}
        where
            academic_year >= {{ var("current_academic_year") - 7 }}
            and testscalescore is not null
    ),

    state_fl as (
        select
            student_id as state_student_id,
            academic_year,
            assessment_subject as subject_area,
            discipline,
            test_code as module_code,
            cast(assessment_grade as int) as grade_level,
            scale_score,
            is_proficient,
            achievement_level as performance_band,
            performance_level as performance_band_level,
            administration_window,
            season,
            assessment_name as title,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            _dbt_source_relation,

            cast(null as date) as test_date,
            cast(null as numeric) as percent_correct,
            cast(null as numeric) as growth_percentile,

            'state_fl' as score_source,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    state_union as (
        select
            nj.student_number,
            nj.academic_year,
            nj.subject_area,
            nj.discipline,
            nj.module_code,
            nj.grade_level,
            nj.scale_score,
            nj.is_proficient,
            nj.performance_band,
            nj.performance_band_level,
            nj.administration_window,
            nj.season,
            nj.title,
            nj.region,
            nj.test_date,
            nj.percent_correct,
            nj.growth_percentile,
            nj.score_source,
            nj._dbt_source_relation,

            cast(null as string) as state_student_id,
        from state_nj as nj

        union all

        select
            cast(null as int64) as student_number,
            fl.academic_year,
            fl.subject_area,
            fl.discipline,
            fl.module_code,
            fl.grade_level,
            fl.scale_score,
            fl.is_proficient,
            fl.performance_band,
            fl.performance_band_level,
            fl.administration_window,
            fl.season,
            fl.title,
            fl.region,
            fl.test_date,
            fl.percent_correct,
            fl.growth_percentile,
            fl.score_source,
            fl._dbt_source_relation,

            fl.state_student_id,
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
                "ia.title",
                "ia.subject_area",
                "ia.scope",
                "ia.module_code",
                "ia.grade_level",
                "ia.administered_date",
                "ia.academic_year",
                "cast(null as string)",
                "ia.region",
                "cast(null as string)",
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
                "su._dbt_source_relation",
                "coalesce(cast(su.student_number as string), su.state_student_id)",
                "su.academic_year",
                "su.administration_window",
                "su.subject_area",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'state'",
                "su.title",
                "su.subject_area",
                "su.discipline",
                "su.module_code",
                "su.grade_level",
                "cast(null as date)",
                "su.academic_year",
                "cast(null as string)",
                "su.region",
                "su.season",
                "su.administration_window",
            ]
        )
    }} as assessment_administration_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "coalesce(cast(su.student_number as string), su.state_student_id)",
            ]
        )
    }} as student_key,

    su.test_date as test_date_key,

    su.scale_score,
    su.percent_correct,
    su.performance_band as proficiency_level,

    su.is_proficient as is_mastery,
from state_union as su
