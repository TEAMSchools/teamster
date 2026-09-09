with
    data_farming as (
        select *, concat('kipp', lower(region)) as _dbt_source_project,
        from {{ source("amplify", "int_amplify__dds__data_farming_unpivot") }}
    ),

    assessments_scores as (
        select
            bss.academic_year,
            bss.region,
            bss.student_primary_id as student_number,
            bss.assessment_grade,
            bss.assessment_grade_int,
            bss.benchmark_period as `period`,
            bss.client_date,
            bss.sync_date,
            bss._dbt_source_project,

            u.surrogate_key,
            u.measure_name,
            u.measure_name_code,
            u.measure_standard,
            u.measure_standard_score,
            u.measure_standard_level,
            u.measure_standard_level_int,
            u.measure_percentile,
            u.measure_semester_growth,
            u.measure_year_growth,

            e.assessment_type,
            e.round_number,
            e.month_round,
            e.start_date,
            e.end_date,
            e.matching_pm_season as matching_season,

        from {{ ref("int_amplify__mclass__benchmark_student_summary") }} as bss
        inner join
            {{ ref("int_amplify__mclass__benchmark_student_summary_unpivot") }} as u
            on bss.surrogate_key = u.surrogate_key
        inner join
            {{ ref("int_google_sheets__dibels_expected_assessments") }} as e
            on bss.academic_year = e.academic_year
            and bss.region = e.region
            and bss.assessment_grade_int = e.grade
            and bss.benchmark_period = e.admin_season
            and u.measure_standard = e.expected_measure_standard
            and e.assessment_type = 'Benchmark'
            and e.assessment_include is null
        where
            bss.enrollment_grade = bss.assessment_grade
            and bss.assessment_grade is not null

        union all

        -- 7/8 benchmark scores SY24 only
        select
            df.academic_year,
            df.region,
            df.student_id as student_number,
            df.assessment_grade,
            df.assessment_grade_int,

            df.period,
            df.`date` as client_date,
            df.`date` as sync_date,
            df._dbt_source_project,

            df.surrogate_key,
            df.measure_name,
            df.measure_name_code,
            df.measure_standard,
            df.measure_standard_score,
            df.measure_standard_level,
            df.measure_standard_level_int,
            df.measure_percentile,

            null as measure_semester_growth,
            null as measure_year_growth,

            e.assessment_type,
            e.round_number,
            e.month_round,
            e.start_date,
            e.end_date,
            e.matching_pm_season as matching_season,

        from data_farming as df
        inner join
            {{ ref("int_google_sheets__dibels_expected_assessments") }} as e
            on df.academic_year = e.academic_year
            and df.region = e.region
            and df.assessment_grade_int = e.grade
            and df.period = e.admin_season
            and df.measure_standard = e.expected_measure_standard
            and e.assessment_type = 'Benchmark'
            and e.assessment_include is null
    ),

    composite_only as (
        select academic_year, student_number, `period`, measure_standard_level,
        from assessments_scores
        where measure_standard = 'Composite'
    ),

    composite_by_window as (
        select *,
        from
            composite_only
            pivot (max(measure_standard_level) for `period` in ('BOY', 'MOY', 'EOY'))
    ),

    probe_eligible_tag as (
        select
            s.*,

            coalesce(c.boy, 'No data') as boy_composite,
            coalesce(c.moy, 'No data') as moy_composite,
            coalesce(c.eoy, 'No data') as eoy_composite,

            if(
                c.boy in ('Below Benchmark', 'Well Below Benchmark'), 'Yes', 'No'
            ) as boy_probe_eligible,

            if(
                c.moy in ('Below Benchmark', 'Well Below Benchmark'), 'Yes', 'No'
            ) as moy_probe_eligible,

        from assessments_scores as s
        left join
            composite_by_window as c
            on s.academic_year = c.academic_year
            and s.student_number = c.student_number
    ),

    custom_composite_labels as (
        select
            *,

            'BM' as model_type,

            case
                period when 'BOY' then 'MOY' when 'MOY' then 'EOY'
            end as benchmark_goal_season,

            case
                when measure_standard_level_int >= 3
                then 'At/Above'
                when measure_standard_level_int <= 2
                then 'Below/Well Below'
            end as aggregated_measure_standard_level,

            case
                when measure_standard_level_int >= 3
                then 'At/Above'
                when measure_standard_level_int = 2
                then 'Below'
                when measure_standard_level_int = 1
                then 'Well Below'
            end as foundation_measure_standard_level,

            if(
                period = 'BOY',
                boy_probe_eligible,
                if(period = 'MOY', moy_probe_eligible, null)
            ) as overall_probe_eligible,

            if(
                period = 'BOY',
                boy_composite,
                if(period = 'MOY', moy_composite, 'No data')
            ) as overall_aimline_composite_level,

            count(*) over (
                partition by
                    academic_year,
                    region,
                    assessment_grade,
                    period,
                    round_number,
                    student_number
            ) as actual_row_count,

        from probe_eligible_tag
    )

select
    *,

    -- one row per student per benchmark administration. The grade is in the
    -- partition because a student can be assessed at two grades within one
    -- benchmark window, and each sitting is its own administration.
    row_number() over (
        partition by academic_year, student_number, `period`, assessment_grade_int
        order by (measure_standard = 'Composite') desc, measure_standard
    ) as rn_pm_eligibility,

from custom_composite_labels
