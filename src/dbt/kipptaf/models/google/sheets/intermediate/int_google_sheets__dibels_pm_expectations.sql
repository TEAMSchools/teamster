with
    -- One row. Shared with int_students__calendar_day so the school side and the
    -- calendar side of the join below cut over on the same year.
    cutover as (
        select focus_start_academic_year, from {{ ref("int_students__sis_cutover") }}
    ),

    school_directory as (
        select
            school_number,
            _dbt_source_project,

            'powerschool' as school_source,

            {{ extract_region("stg_powerschool__schools") }} as region,

            _dbt_source_project = 'kippmiami' as is_focus_sis_region,

        from {{ ref("stg_powerschool__schools") }}
        where state_excludefromreporting = 0

        union all

        select
            loc.powerschool_school_id as school_number,

            f._dbt_source_project,

            'focus' as school_source,

            {{ extract_region("f") }} as region,

            true as is_focus_sis_region,

        from {{ ref("int_focus__schools") }} as f
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on f.school_number = loc.focus_school_id
            and not loc.is_pathways
        where f.max_syear is null
    ),

    pm_rounds as (
        select
            s.region,

            t.academic_year,
            t.name as term_name,

            safe_cast(regexp_extract(t.code, r'LIT(\d+)') as int) as round_number,

            count(distinct c.date_value) as pm_round_days,

        from school_directory as s
        -- Not stg_powerschool__calendar_day: Miami is Focus-only from AY2026, and
        -- the frozen PowerSchool archive still serves a rolled-forward Miami
        -- calendar (phantom in-session days in Jul 2026, Aug 3-11, Jun 4-29) that
        -- would shift PM round boundaries. int_students__calendar_day substitutes
        -- Focus for Focus-covered years and is day-for-day identical for NJ.
        inner join
            {{ ref("int_students__calendar_day") }} as c
            on s.school_number = c.schoolid
            and c.insession = 1
            and s._dbt_source_project = c._dbt_source_project
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as t
            on s.region = t.region
            and c.date_value between t.start_date and t.end_date
            and t.type = 'LIT'
            and t.name in ('BOY->MOY', 'MOY->EOY')
        cross join cutover as cut
        -- Miami's SIS boundary is a YEAR boundary, not a source swap: rows for
        -- SY25-26 and prior come from the frozen PowerSchool archive, rows from
        -- SY26-27 onward come from Focus. Dropping Miami from the PowerSchool
        -- branch outright would erase its AY2024/AY2025 PM history.
        where
            case
                when s.school_source = 'focus'
                then t.academic_year >= cut.focus_start_academic_year
                when s.is_focus_sis_region
                then t.academic_year < cut.focus_start_academic_year
                else true
            end
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

    t.code,
    t.start_date,
    t.end_date,

    d.pm_round_days,
    d.pm_days,

    g.admin_season as benchmark_season,
    g.grade_level_standard as benchmark_goal,

from {{ ref("int_google_sheets__dibels_expected_assessments") }} as e
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as t
    on e.academic_year = t.academic_year
    and e.region = t.region
    and e.admin_season = t.name
    and e.test_code = t.code
    and e.assessment_type = 'PM'
    and t.type = 'LIT'
left join
    pm_rounds_agg as d
    on t.academic_year = d.academic_year
    and t.region = d.region
    and t.name = d.term_name
    and e.round_number = d.round_number
left join
    {{ ref("stg_google_sheets__dibels_goals_long") }} as g
    on e.expected_measure_standard = g.measure_standard
    and e.grade = g.grade_level
    and e.admin_season = g.matching_pm_season
{# TODO: update to current_school_year var #}
where e.academic_year >= 2025
