with
    pm_rounds as (
        select
            s.region,

            t.academic_year,
            t.name as term_name,

            -- anchored, and P?LIT matches PLIT deliberately
            safe_cast(regexp_extract(t.code, r'^P?LIT(\d+)$') as int) as round_number,

            count(distinct c.date_value) as pm_round_days,

        -- the directory is school x grade x year; count(distinct) absorbs the
        -- grade fan-out
        from {{ ref("int_students__school_directory") }} as s
        -- SIS-neutral, not stg_powerschool__calendar_day: Miami is Focus-only
        inner join
            {{ ref("int_students__calendar_day") }} as c
            on s.ps_schoolid = c.schoolid
            and c.insession = 1
            and s._dbt_source_project = c._dbt_source_project
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as t
            on s.region = t.region
            and s.academic_year = t.academic_year
            and c.date_value between t.start_date and t.end_date
            and t.type = 'LIT'
            and t.name in ('BOY->MOY', 'MOY->EOY')
        -- no calendar to count: recruiting rows, and DIBELS is K-8
        where s.school_source != 'finalsite' and s.school_level_alt != 'HS'
        group by s.region, t.academic_year, t.name, round_number
    ),

    pm_rounds_agg as (
        select
            *,

            sum(pm_round_days) over (
                partition by academic_year, region, term_name
            ) as pm_days,

        from pm_rounds
    )

select
    e.academic_year,
    e.region,
    e.grade,
    e.admin_season,
    e.round_number,
    e.min_pm_round,
    e.max_pm_round,
    e.month_round,
    e.expected_measure_name_code,
    e.expected_measure_name,
    e.expected_measure_standard,
    e.pm_goal_include,
    e.pm_goal_criteria,

    e.test_code as code,
    e.start_date,
    e.end_date,

    d.pm_round_days,
    d.pm_days,

    g.admin_season as benchmark_season,
    g.grade_level_standard as benchmark_goal,

from {{ ref("int_google_sheets__dibels_expected_assessments") }} as e
left join
    pm_rounds_agg as d
    on e.academic_year = d.academic_year
    and e.region = d.region
    and e.admin_season = d.term_name
    and e.round_number = d.round_number
left join
    {{ ref("stg_google_sheets__dibels_goals_long") }} as g
    on e.expected_measure_standard = g.measure_standard
    and e.grade = g.grade_level
    and e.admin_season = g.matching_pm_season
where
    e.assessment_type = 'PM'
    -- no term row covers this grade, so the round has no window
    and e.start_date is not null
