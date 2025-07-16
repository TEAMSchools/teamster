with
    avg_scores as (
        select
            academic_year,
            region,
            assessment_grade,
            assessment_grade_int,
            period,
            matching_season,
            measure_standard,

            round(avg(measure_standard_score), 0) as starting_words,

        from {{ ref("int_amplify__all_assessments") }}
        where
            academic_year = 2024
            and measure_standard != 'Composite'
            and overall_probe_eligible = 'Yes'
            and period in ('BOY', 'MOY')
        group by
            academic_year,
            region,
            assessment_grade,
            assessment_grade_int,
            period,
            matching_season,
            measure_standard,
            overall_probe_eligible
    ),

    scores_and_days as (
        select
            a.academic_year,
            a.region,
            a.assessment_grade,
            a.assessment_grade_int,
            a.period,
            a.matching_season,
            a.measure_standard,
            a.starting_words,

            e.code,
            e.`round`,
            e.pm_round_days,
            e.pm_days,
            e.pm_goal_include,

            e.benchmark_goal + 3 as benchmark_goal,

            round(
                (e.benchmark_goal + 3) - a.starting_words, 0
            ) as required_growth_words,

            if(e.`round` = e.min_pm_round, true, false) as is_min_round,

            if(e.`round` = e.max_pm_round, true, false) as is_max_round,

        from avg_scores as a
        inner join
            {{ ref("int_google_sheets__dibels_pm_expectations") }} as e
            on a.academic_year = e.academic_year
            and a.region = e.region
            and a.assessment_grade_int = e.grade
            and a.matching_season = e.admin_season
            and a.measure_standard = e.expected_measure_standard
    ),

    calcs as (
        select
            academic_year,
            region,
            assessment_grade,
            assessment_grade_int,
            period,
            matching_season,
            measure_standard,
            starting_words,
            code,
            `round`,
            pm_round_days,
            pm_days,
            pm_goal_include,
            benchmark_goal,
            required_growth_words,
            is_max_round,

            round(safe_divide(required_growth_words, pm_days), 2) as daily_growth_rate,

            round(
                case
                    when is_min_round
                    then
                        safe_divide((pm_round_days * required_growth_words), pm_days)
                        + starting_words
                    else safe_divide((pm_round_days * required_growth_words), pm_days)
                end,
                0
            ) as round_growth_words_goal,

        from scores_and_days
    )

select
    *,

    case
        when is_max_round
        then benchmark_goal
        else
            sum(round_growth_words_goal) over (
                partition by
                    academic_year,
                    region,
                    matching_season,
                    assessment_grade_int,
                    measure_standard
                order by
                    academic_year,
                    region,
                    matching_season,
                    `round`,
                    assessment_grade_int,
                    measure_standard
            )
    end as cumulative_growth_words,

from calcs
