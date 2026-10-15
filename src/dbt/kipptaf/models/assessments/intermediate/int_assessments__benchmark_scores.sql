with
    unioned as (
        select
            _dbt_source_project,
            student_id as student_number,
            academic_year_int as academic_year,
            test_round as administration_period,
            completion_date as test_date,
            `subject` as raw_subject,
            `subject` as module_code,
            discipline,

            cast(overall_scale_score as numeric) as scale_score,
            cast(percentile as numeric) as national_percentile,

            overall_relative_placement as proficiency_level,
            overall_relative_placement_int as proficiency_level_int,

            overall_relative_placement_int >= 4 as is_mastery,

            is_proficient,

            'overall' as response_type,

            cast(null as string) as response_type_code,
            cast(null as string) as response_type_description,

            rn_subj_day,
            rn_subj_round,

            cast(null as string) as assessment_id,

            'iready' as score_source,
            'iready' as source_system,
        from {{ ref("int_assessments__iready_diagnostic_results") }}

        union all

        select
            _dbt_source_project,
            student_display_id as student_number,
            academic_year,
            screening_period_window_name as administration_period,
            completed_date_value as test_date,
            _dagster_partition_subject as raw_subject,
            star_subject as module_code,

            cast(null as string) as discipline,
            cast(unified_score as numeric) as scale_score,
            cast(percentile_rank as numeric) as national_percentile,

            state_benchmark_category_name as proficiency_level,

            cast(null as int64) as proficiency_level_int,

            state_benchmark_proficient = 'Yes' as is_mastery,

            cast(null as bool) as is_proficient,

            'overall' as response_type,

            cast(null as string) as response_type_code,
            cast(null as string) as response_type_description,
            cast(null as int64) as rn_subj_day,
            cast(null as int64) as rn_subj_round,

            assessment_id,

            'star' as score_source,
            'renlearn' as source_system,
        from {{ ref("stg_renlearn__star") }}

        union all

        select
            _dbt_source_project,
            student_number,
            academic_year,
            `period` as administration_period,
            client_date as test_date,

            'DIBELS' as raw_subject,
            'Composite' as module_code,

            cast(null as string) as discipline,
            cast(measure_standard_score as numeric) as scale_score,
            cast(measure_percentile as numeric) as national_percentile,

            measure_standard_level as proficiency_level,
            measure_standard_level_int as proficiency_level_int,

            measure_standard_level_int >= 3 as is_mastery,

            aggregated_measure_standard_level = 'At/Above' as is_proficient,

            if(measure_standard = 'Composite', 'overall', 'group') as response_type,

            case
                when measure_standard != 'Composite' then measure_standard
            end as response_type_code,

            case
                when measure_standard != 'Composite' then measure_name
            end as response_type_description,

            cast(null as int64) as rn_subj_day,
            cast(null as int64) as rn_subj_round,
            cast(null as string) as assessment_id,

            'dibels' as score_source,
            'amplify' as source_system,
        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark'
    )

select
    u.score_source,
    u.source_system,
    u._dbt_source_project,
    u.student_number,
    u.academic_year,
    u.administration_period,
    u.test_date,
    u.raw_subject,
    u.module_code,
    u.discipline,
    u.scale_score,
    u.national_percentile,
    u.proficiency_level,
    u.proficiency_level_int,
    u.is_mastery,
    u.is_proficient,
    u.response_type,
    u.response_type_code,
    u.response_type_description,
    u.rn_subj_day,
    u.rn_subj_round,
    u.assessment_id,

    coalesce(x.illuminate_subject_area, u.raw_subject) as illuminate_subject_area,
from unioned as u
left join
    {{ ref("stg_google_sheets__assessments__vendor_subject_crosswalk") }} as x
    on u.source_system = x.source_system
    and u.raw_subject = x.raw_subject
