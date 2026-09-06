with
    -- grain projection, not dup-masking: the directory is school x grade x year
    -- and PM days are counted per school-year, so grade level drops out
    school_years as (
        select distinct _dbt_source_project, academic_year, region, ps_schoolid,

        from {{ ref("int_students__school_directory") }}
        -- Finalsite rows are next year's recruiting, not a year students
        -- attended, so there is no calendar to count days in.
        where school_source != 'finalsite' and school_level_alt != 'HS'
    ),

    pm_rounds as (
        select
            s.region,

            t.academic_year,
            t.name as term_name,

            -- P?LIT, anchored: a round's day count is its LIT testing window
            -- PLUS its PLIT instructional window, and PLIT supplies most of it.
            -- Anchoring keeps that deliberate instead of relying on LIT
            -- matching inside PLIT, which any future code containing LIT would
            -- also do.
            safe_cast(regexp_extract(t.code, r'^P?LIT(\d+)$') as int) as round_number,

            count(distinct c.date_value) as pm_round_days,

        from school_years as s
        -- Not stg_powerschool__calendar_day: Miami is Focus-only from AY2026, and
        -- the frozen PowerSchool archive still serves a rolled-forward Miami
        -- calendar (phantom in-session days in Jul 2026, Aug 3-11, Jun 4-29) that
        -- would shift PM round boundaries. int_students__calendar_day substitutes
        -- Focus for Focus-covered years and is day-for-day identical for NJ.
        inner join
            {{ ref("int_students__calendar_day") }} as c
            on s.ps_schoolid = c.schoolid
            and c.insession = 1
            and s._dbt_source_project = c._dbt_source_project
        -- s.academic_year = t.academic_year is the Miami SIS boundary, and it
        -- needs no cutover year: the directory already assigns Miami's SY25-26
        -- and prior to PowerSchool and SY26-27 onward to Focus, so a school only
        -- contributes days to years it actually enrolled students in.
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as t
            on s.region = t.region
            and s.academic_year = t.academic_year
            and c.date_value between t.start_date and t.end_date
            and t.type = 'LIT'
            and t.name in ('BOY->MOY', 'MOY->EOY')
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
    -- internal only. The aimline calculation needs no day count and compares a
    -- per-student aimline rather than a cohort trajectory, so it gets its own
    -- models rather than sharing this one behind a discriminator.
    and e.data_model = 'internal'
    -- the window comes from upstream, which resolves it per grade against the
    -- row's own band. Re-joining reporting__terms here would match every band.
    -- A null window means no term row covers this grade, which is what the
    -- inner join to terms used to drop.
    and e.start_date is not null
