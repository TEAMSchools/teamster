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
        where s.state_excludefromreporting = 0
    ),

    day_count as (
        select
            t.academic_year,
            t.region,
            t.name,

            cast(right(t.code, 1) as int) as `round`,

            count(distinct d.date_value) n_days,

        from school_directory as d
        left join
            {{ ref("stg_reporting__terms") }} as t
            on d.region = t.region
            and d.date_value between t.start_date and t.end_date
            and d.region_distinct = 1
            and t.type = 'LIT'
            and t.region = 'Camden'
            and t.name != 'EOY'
            and t.academic_year = {{ var("current_academic_year") }}
        where t.academic_year is not null
        group by all
    ),

    avg_scores as (
        select
            s.mclass_academic_year,
            s.mclass_assessment_grade,
            s.mclass_assessment_grade_int,
            s.mclass_period,
            s.mclass_measure_standard,

            e.region,

            concat(s.mclass_period, s.mclass_measure_standard) as filter_tag,

            if(s.mclass_period = 'BOY', 'BOY->MOY', 'MOY->EOY') as pm_period,

            avg(s.mclass_measure_standard_score) as avg_score_raw,

            round(avg(s.mclass_measure_standard_score), 0) as avg_score,

        from {{ ref("int_amplify__all_assessments") }} as s
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on s.mclass_academic_year = e.academic_year
            and s.mclass_student_number = e.student_number
        where
            s.mclass_academic_year = {{ var("current_academic_year") }}
            and s.assessment_type = 'Benchmark'
            and s.mclass_period != 'EOY'
            and s.mclass_assessment_grade_int is not null
            and mclass_measure_standard in (
                'Phonemic Awareness (PSF)',
                'Letter Sounds (NWF-CLS)',
                'Decoding (NWF-WRC)',
                'Reading Fluency (ORF)',
                'Reading Accuracy (ORF-Accu)'
            )
            and (
                (
                    s.mclass_period = 'BOY'
                    and s.boy_composite in ('Below Benchmark', 'Well Below Benchmark')
                )
                or (
                    s.mclass_period = 'MOY'
                    and s.moy_composite in ('Below Benchmark', 'Well Below Benchmark')
                )
            )
            and e.region is not null
        group by all
    ),

    /* this will be simplified once we figure out how to calculate bm_benchmark on the fly */
    days_and_goals as (
        -- only need this distinct for now because standard are not the same across
        -- rounds
        select distinct
            s.mclass_academic_year,
            s.region,
            s.pm_period,
            s.mclass_assessment_grade,
            s.mclass_assessment_grade_int,
            s.mclass_measure_standard,
            s.avg_score as starting_words,

            c.round,
            c.n_days,

            (coalesce(e.moy_benchmark, e.eoy_benchmark) + 3) as bm_benchmark,

            round(
                (coalesce(e.moy_benchmark, e.eoy_benchmark) + 3) - s.avg_score, 0
            ) as required_growth_words,

            min(c.round) over (
                partition by
                    s.mclass_academic_year,
                    s.region,
                    s.pm_period,
                    s.mclass_assessment_grade
                order by c.round
            ) as min_pm_round,

            max(c.round) over (
                partition by
                    s.mclass_academic_year,
                    s.region,
                    s.pm_period,
                    s.mclass_assessment_grade
                order by c.round desc
            ) as max_pm_round,

        from avg_scores as s
        inner join
            day_count as c
            on s.mclass_academic_year = c.academic_year
            and s.region = c.region
            and s.pm_period = name
        inner join
            {{ ref("stg_amplify__dibels_pm_expectations") }} as e
            on s.mclass_academic_year = e.academic_year
            and s.region = e.region
            and s.pm_period = e.period
            and s.mclass_assessment_grade_int = e.grade_level
            and s.mclass_measure_standard = e.measure_standard
            and s.filter_tag in (
                'BOYPhonemic Awareness (PSF)',
                'MOYDecoding (NWF-WRC)',
                'MOYLetter Sounds (NWF-CLS)',
                'MOYReading Fluency (ORF)',
                'MOYReading Accuracy (ORF-Accu)'
            )
        where s.region = 'Camden'
    ),

    calcs as (
        select
            *,

            if(`round` = min_pm_round, true, false) as is_min_round,

            if(`round` = max_pm_round, true, false) as is_max_round,

            sum(n_days) over (
                partition by
                    mclass_academic_year,
                    region,
                    pm_period,
                    mclass_assessment_grade_int,
                    mclass_measure_standard
            ) as pm_n_days,

            round(
                required_growth_words / sum(n_days) over (
                    partition by
                        mclass_academic_year,
                        region,
                        pm_period,
                        mclass_assessment_grade_int,
                        mclass_measure_standard
                ),
                1
            ) as daily_growth_rate,

            round(
                case
                    when `round` = min_pm_round
                    then
                        (n_days * required_growth_words) / sum(n_days) over (
                            partition by
                                mclass_academic_year,
                                region,
                                pm_period,
                                mclass_assessment_grade_int,
                                mclass_measure_standard
                        )
                        + starting_words
                    else
                        (n_days * required_growth_words) / sum(n_days) over (
                            partition by
                                mclass_academic_year,
                                region,
                                pm_period,
                                mclass_assessment_grade_int,
                                mclass_measure_standard
                        )
                end,
                0
            ) as round_growth_words_goal,

        from days_and_goals
    ),

    custom_calc as (
        select
            *,

            case
                when is_max_round
                then bm_benchmark
                else
                    sum(round_growth_words_goal) over (
                        partition by
                            mclass_academic_year,
                            region,
                            pm_period,
                            mclass_assessment_grade_int,
                            mclass_measure_standard
                        order by
                            mclass_academic_year,
                            region,
                            pm_period,
                            `round`,
                            mclass_assessment_grade_int,
                            mclass_measure_standard
                        rows between unbounded preceding and current row
                    )
            end as cumulative_growth_words

        from calcs
    )

select *,
from custom_calc
order by
    mclass_academic_year,
    region,
    pm_period,
    mclass_assessment_grade_int,
    mclass_measure_standard,
    `round`
