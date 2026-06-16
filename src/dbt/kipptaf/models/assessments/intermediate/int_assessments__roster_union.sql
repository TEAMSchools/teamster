with
    iready_filtered as (
        select
            student_id,
            academic_year_int,
            subject,
            test_round,
            overall_scale_score,
            overall_relative_placement,
            overall_relative_placement_int,
            is_proficient,
            completion_date,
        from {{ ref("int_iready__diagnostic_results") }}
        where
            subject in ('Reading', 'Math')
            and academic_year_int in (
                {{ var("current_academic_year") }},
                {{ var("current_academic_year") - 1 }}
            )
    ),

    -- a student can take more than one diagnostic within a round; keep the latest
    iready_deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="iready_filtered",
                partition_by="student_id, academic_year_int, subject, test_round",
                order_by="completion_date desc",
            )
        }}
    ),

    iready as (
        select
            student_id as student_number,
            academic_year_int as academic_year,
            test_round as administration_round,
            overall_relative_placement as performance_band_label,
            overall_relative_placement_int as performance_band_int,
            is_proficient,

            'i-Ready' as assessment_source,

            cast(null as string) as assessment_id,
            cast(null as string) as assessment_title,
            cast(overall_scale_score as numeric) as scale_score,
            cast(null as numeric) as percent_correct,

            case
                `subject` when 'Reading' then 'ELA' when 'Math' then 'Math'
            end as `subject`,
        from iready_deduplicated
    ),

    fast as (
        select
            student_number,
            academic_year,
            administration_window as administration_round,
            achievement_level as performance_band_label,
            performance_level as performance_band_int,
            is_proficient,

            'FAST' as assessment_source,

            cast(null as string) as assessment_id,
            cast(null as string) as assessment_title,
            cast(scale_score as numeric) as scale_score,
            cast(null as numeric) as percent_correct,

            case
                illuminate_subject
                when 'Text Study'
                then 'ELA'
                when 'Mathematics'
                then 'Math'
            end as `subject`,
        from {{ ref("int_fldoe__all_assessments") }}
        where
            student_number is not null
            and illuminate_subject in ('Text Study', 'Mathematics')
            and academic_year in (
                {{ var("current_academic_year") }},
                {{ var("current_academic_year") - 1 }}
            )
    ),

    dibels_filtered as (
        select
            student_number,
            academic_year,
            period,
            measure_standard_score,
            measure_standard_level,
            measure_standard_level_int,
            aggregated_measure_standard_level,
            client_date,
        from {{ ref("int_amplify__all_assessments") }}
        where
            assessment_type = 'Benchmark'
            and measure_standard = 'Composite'
            and academic_year in (
                {{ var("current_academic_year") }},
                {{ var("current_academic_year") - 1 }}
            )
    ),

    -- a student can take more than one benchmark within a round; keep the latest
    dibels_deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="dibels_filtered",
                partition_by="student_number, academic_year, period",
                order_by="client_date desc",
            )
        }}
    ),

    dibels as (
        select
            student_number,
            academic_year,
            period as administration_round,
            measure_standard_level as performance_band_label,
            measure_standard_level_int as performance_band_int,

            'DIBELS' as assessment_source,
            'ELA' as `subject`,

            cast(null as string) as assessment_id,
            cast(null as string) as assessment_title,
            cast(measure_standard_score as numeric) as scale_score,
            cast(null as numeric) as percent_correct,

            aggregated_measure_standard_level = 'At/Above' as is_proficient,
        from dibels_deduplicated
    ),

    njsla as (
        select
            localstudentidentifier as student_number,
            academic_year,
            admin as administration_round,
            testperformancelevel_text as performance_band_label,
            is_proficient,

            'NJSLA' as assessment_source,

            cast(null as string) as assessment_id,
            cast(null as string) as assessment_title,
            cast(testscalescore as numeric) as scale_score,
            cast(null as numeric) as percent_correct,
            cast(testperformancelevel as int) as performance_band_int,

            case
                illuminate_subject
                when 'Text Study'
                then 'ELA'
                when 'Mathematics'
                then 'Math'
            end as `subject`,
        from {{ ref("int_pearson__all_assessments") }}
        where
            assessment_name = 'NJSLA'
            and illuminate_subject in ('Text Study', 'Mathematics')
            and academic_year = {{ var("current_academic_year") - 1 }}
    ),

    internal as (
        select
            powerschool_student_number as student_number,
            academic_year,
            module_code as administration_round,
            performance_band_label,
            `discipline` as `subject`,
            is_mastery as is_proficient,

            'Internal' as assessment_source,

            cast(null as numeric) as scale_score,
            percent_correct,
            cast(assessment_id as string) as assessment_id,
            title as assessment_title,
            cast(performance_band_label_number as int) as performance_band_int,
        from {{ ref("int_assessments__response_rollup") }}
        where
            module_type in ('QA', 'MQQ', 'CRQ')
            and response_type = 'overall'
            and `discipline` in ('ELA', 'Math')
            and academic_year in (
                {{ var("current_academic_year") }},
                {{ var("current_academic_year") - 1 }}
            )
    ),

    unioned as (
        select
            student_number,
            academic_year,
            administration_round,
            performance_band_label,
            performance_band_int,
            is_proficient,
            assessment_source,
            assessment_id,
            assessment_title,
            scale_score,
            percent_correct,
            `subject`,
        from iready

        union all

        select
            student_number,
            academic_year,
            administration_round,
            performance_band_label,
            performance_band_int,
            is_proficient,
            assessment_source,
            assessment_id,
            assessment_title,
            scale_score,
            percent_correct,
            `subject`,
        from fast

        union all

        select
            student_number,
            academic_year,
            administration_round,
            performance_band_label,
            performance_band_int,
            is_proficient,
            assessment_source,
            assessment_id,
            assessment_title,
            scale_score,
            percent_correct,
            `subject`,
        from dibels

        union all

        select
            student_number,
            academic_year,
            administration_round,
            performance_band_label,
            performance_band_int,
            is_proficient,
            assessment_source,
            assessment_id,
            assessment_title,
            scale_score,
            percent_correct,
            `subject`,
        from njsla

        union all

        select
            student_number,
            academic_year,
            administration_round,
            performance_band_label,
            performance_band_int,
            is_proficient,
            assessment_source,
            assessment_id,
            assessment_title,
            scale_score,
            percent_correct,
            `subject`,
        from internal
    )

select
    *,
    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "academic_year",
                "assessment_source",
                "subject",
                "administration_round",
                "coalesce(assessment_id, 'none')",
            ]
        )
    }} as surrogate_key,
from unioned
