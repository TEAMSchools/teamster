with
    school_directory as (
        select
            s.schoolcity as region,
            s.school_number as schoolid,
            s.abbreviation as school,

            c.date_value,

            row_number() over (
                partition by s.schoolcity, c.date_value
            ) as region_distinct,

        from {{ ref("stg_powerschool__schools") }} as s
        inner join
            {{ ref("stg_powerschool__calendar_day") }} as c
            on s.school_number = c.schoolid
            and c.insession = 1
            and {{ union_dataset_join_clause(left_alias="s", right_alias="c") }}
        where s.state_excludefromreporting = 0
        qualify region_distinct = 1
    ),

    custom_pm_reporting as (
        select
            t.academic_year,
            t.region,
            t.name,

            cast(right(t.code, 1) as int) as `round`,

            d.date_value,

        from school_directory as d
        inner join
            {{ ref("stg_reporting__terms") }} as t
            on d.region = t.region
            and d.date_value between t.start_date and t.end_date
            and t.type = 'LIT'
            and t.name != 'EOY'
            and t.academic_year = {{ var("current_academic_year") }}
    ),

    day_count as (
        select
            academic_year, region, name, `round`, count(distinct date_value) as n_days,

        from custom_pm_reporting
        group by academic_year, region, name, `round`
    ),

    avg_scores as (
        select
            s.academic_year,
            s.assessment_grade,
            s.assessment_grade_int,
            s.period,
            s.measure_standard,

            e.region,

            concat(s.period, s.measure_standard) as filter_tag,

            if(s.period = 'BOY', 'BOY->MOY', 'MOY->EOY') as pm_period,

            avg(s.measure_standard_score) as avg_score_raw,

            round(avg(s.measure_standard_score), 0) as avg_score,

        from {{ ref("int_amplify__all_assessments") }} as s
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on s.academic_year = e.academic_year
            and s.student_number = e.student_number
        where
            s.academic_year = {{ var("current_academic_year") }}
            and s.assessment_type = 'Benchmark'
            and s.period != 'EOY'
            and s.assessment_grade_int is not null
            and s.measure_standard in (
                'Phonemic Awareness (PSF)',
                'Letter Sounds (NWF-CLS)',
                'Decoding (NWF-WRC)',
                'Reading Fluency (ORF)',
                'Reading Accuracy (ORF-Accu)'
            )
            and (
                (
                    s.period = 'BOY'
                    and s.boy_composite in ('Below Benchmark', 'Well Below Benchmark')
                )
                or (
                    s.period = 'MOY'
                    and s.moy_composite in ('Below Benchmark', 'Well Below Benchmark')
                )
            )
        group by
            s.academic_year,
            s.assessment_grade,
            s.assessment_grade_int,
            s.period,
            s.measure_standard,
            e.region
    ),

    pm_expectations as (
        /* TODO: lookup table needs to be refactored */
        select distinct
            academic_year,
            region,
            `period`,
            grade_level,
            measure_standard,
            moy_benchmark,
            eoy_benchmark,
        from {{ ref("stg_google_sheets__dibels_pm_expectations") }}
    ),

    /* this will be simplified once we figure out how to calculate bm_benchmark on the
    fly */
    days_and_goals as (
        select
            s.academic_year,
            s.region,
            s.pm_period,
            s.assessment_grade,
            s.assessment_grade_int,
            s.measure_standard,
            s.avg_score as starting_words,

            c.round,
            c.n_days,

            (coalesce(e.moy_benchmark, e.eoy_benchmark) + 3) as bm_benchmark,

            round(
                (coalesce(e.moy_benchmark, e.eoy_benchmark) + 3) - s.avg_score, 0
            ) as required_growth_words,

            min(c.round) over (
                partition by s.academic_year, s.region, s.pm_period, s.assessment_grade
                order by c.`round`
            ) as min_pm_round,

            max(c.`round`) over (
                partition by s.academic_year, s.region, s.pm_period, s.assessment_grade
                order by c.`round` desc
            ) as max_pm_round,
        from avg_scores as s
        inner join
            day_count as c
            on s.academic_year = c.academic_year
            and s.region = c.region
            and s.pm_period = c.name
        inner join
            pm_expectations as e
            on s.academic_year = e.academic_year
            and s.region = e.region
            and s.pm_period = e.period
            and s.assessment_grade_int = e.grade_level
            and s.measure_standard = e.measure_standard
        where
            s.filter_tag in (
                'BOYPhonemic Awareness (PSF)',
                'MOYDecoding (NWF-WRC)',
                'MOYLetter Sounds (NWF-CLS)',
                'MOYReading Fluency (ORF)',
                'MOYReading Accuracy (ORF-Accu)'
            )
    ),

    calcs as (
        select
            *,

            if(`round` = min_pm_round, true, false) as is_min_round,

            if(`round` = max_pm_round, true, false) as is_max_round,

            sum(n_days) over (
                partition by
                    academic_year,
                    region,
                    pm_period,
                    assessment_grade_int,
                    measure_standard
            ) as pm_n_days,

            round(
                required_growth_words / sum(n_days) over (
                    partition by
                        academic_year,
                        region,
                        pm_period,
                        assessment_grade_int,
                        measure_standard
                ),
                2
            ) as daily_growth_rate,

            round(
                case
                    when `round` = min_pm_round
                    then
                        (n_days * required_growth_words) / sum(n_days) over (
                            partition by
                                academic_year,
                                region,
                                pm_period,
                                assessment_grade_int,
                                measure_standard
                        )
                        + starting_words
                    else
                        (n_days * required_growth_words) / sum(n_days) over (
                            partition by
                                academic_year,
                                region,
                                pm_period,
                                assessment_grade_int,
                                measure_standard
                        )
                end,
                0
            ) as round_growth_words_goal,
        from days_and_goals
    )

select
    *,

    case
        when is_max_round
        then bm_benchmark
        else
            sum(round_growth_words_goal) over (
                partition by
                    academic_year,
                    region,
                    pm_period,
                    assessment_grade_int,
                    measure_standard
                order by
                    academic_year,
                    region,
                    pm_period,
                    `round`,
                    assessment_grade_int,
                    measure_standard
                rows between unbounded preceding and current row
            )
    end as cumulative_growth_words,
from calcs
