with
    enrolled_composites as (
        select
            a.academic_year,
            a.region,
            a.assessment_grade_int as grade_level,
            a.period,
            a.foundation_measure_standard_level,
            a.is_above_average_growth,

            s.student_number,
            s.iep_status,
            s.lep_status,

        from {{ ref("int_amplify__all_assessments") }} as a
        inner join
            {{ ref("int_extracts__student_enrollments_subjects") }} as s
            on a.academic_year = s.academic_year
            and a.region = s.region
            and a.student_number = s.student_number
            and a.assessment_grade_int = s.grade_level
            and a.client_date between s.entrydate and s.exitdate
        where
            a.assessment_type = 'Benchmark'
            and a.measure_standard = 'Composite'
            and s.iready_subject = 'Reading'
            and not s.is_self_contained
            and not s.is_out_of_district
            and s.enroll_status in (0, 2, 3)
    ),

    population_fanout as (
        select
            academic_year,
            region,
            grade_level,
            `period`,
            foundation_measure_standard_level,
            is_above_average_growth,
            student_number,

            population,

        from enrolled_composites
        cross join
            unnest(
                array_concat(
                    ['All'],
                    if(iep_status = 'Has IEP', ['IEP'], []),
                    if(lep_status, ['MLL'], [])
                )
            ) as population
    ),

    school_grade_population_counts as (
        select
            academic_year,
            region,
            grade_level,
            `period`,
            population,

            count(student_number) as n_all,
            countif(foundation_measure_standard_level = 'At/Above') as n_at_above,
            countif(foundation_measure_standard_level = 'Well Below') as n_well_below,
            countif(is_above_average_growth) as n_above_average_growth,

        from population_fanout
        group by academic_year, region, grade_level, `period`, population
    ),

    goal_type_rows as (
        select
            c.academic_year,
            c.region,
            c.grade_level,
            c.period,
            c.population,

            c.n_all,
            c.n_above_average_growth,

            goal_type,

            if(goal_type = 'At/Above', c.n_at_above, c.n_well_below) as n_attained,

        from school_grade_population_counts as c
        cross join unnest(['At/Above', 'Well Below']) as goal_type
    ),

    attainment as (
        select
            *,

            safe_divide(n_attained, n_all) as attained_rate,

            -- Above-average growth doesn't exist yet at BOY (no prior period
            -- to grow from), so the rate is null there rather than a
            -- misleading 0%. This is Amplify's own national-norm growth
            -- flag, not a rate against our own population's average growth
            -- -- see the dibels-dashboard skill for why those are different
            -- asks and only the former is built today.
            if(
                `period` = 'BOY', null, safe_divide(n_above_average_growth, n_all)
            ) as pct_above_average_growth,

        from goal_type_rows
    ),

    goals_joined as (
        select
            a.academic_year,
            a.region,
            a.grade_level,
            a.period,
            a.population,
            a.goal_type,

            f.grade_band,

            a.n_all,
            a.n_attained,
            a.attained_rate,
            a.n_above_average_growth,
            a.pct_above_average_growth,
            f.grade_goal,

        from attainment as a
        inner join
            {{ ref("stg_google_sheets__dibels_foundation_goals") }} as f
            on a.academic_year = f.academic_year
            and a.region = f.region
            and a.grade_level = f.grade_level
            and a.period = f.period
            and a.population = f.population
            and a.goal_type = f.grade_goal_type
    ),

    gap_calc as (
        select
            *,

            round(
                if(
                    goal_type = 'At/Above',
                    (attained_rate - grade_goal) * 100,
                    (grade_goal - attained_rate) * 100
                ),
                0
            ) as gap,

        from goals_joined
    )

select
    g.academic_year,
    g.region,
    g.grade_level,
    g.period,
    g.population,
    g.goal_type,
    g.grade_band,

    t.tier as brightspot_status,

    g.n_all,
    g.n_attained,
    g.attained_rate,
    g.grade_goal,
    g.gap,
    g.n_above_average_growth,
    g.pct_above_average_growth,

from gap_calc as g
inner join
    {{ ref("stg_google_sheets__dibels_brightspot_goals") }} as t
    on g.academic_year = t.academic_year
    and g.grade_band = t.grade_band
    and g.period = t.period
    and g.population = t.population
    and (t.gap_min is null or g.gap >= t.gap_min)
    and (t.gap_max is null or g.gap <= t.gap_max)
