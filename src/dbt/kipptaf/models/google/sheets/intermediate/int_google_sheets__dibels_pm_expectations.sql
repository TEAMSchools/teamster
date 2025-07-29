with
    pm_round_days as (
        select
            s.schoolcity as region,

            t.academic_year,
            t.name,

            safe_cast(right(t.code, 1) as int64) as `round`,

            count(distinct c.date_value) over (
                partition by t.academic_year, s.schoolcity, t.name, right(t.code, 1)
            ) as pm_round_days,

            count(distinct c.date_value) over (
                partition by t.academic_year, s.schoolcity, t.name
            ) as pm_days,

        from {{ ref("stg_powerschool__schools") }} as s
        inner join
            {{ ref("stg_powerschool__calendar_day") }} as c
            on s.school_number = c.schoolid
            and c.insession = 1
            and {{ union_dataset_join_clause(left_alias="s", right_alias="c") }}
        inner join
            {{ ref("stg_reporting__terms") }} as t
            on s.schoolcity = t.region
            and c.date_value between t.start_date and t.end_date
            and t.type = 'LIT'
            and t.name in ('BOY->MOY', 'MOY->EOY')
        where s.state_excludefromreporting = 0
    ),

    final as (
        select
            e.academic_year,
            e.region,
            e.grade,
            e.admin_season,
            e.`round`,
            e.min_pm_round,
            e.max_pm_round,
            e.expected_measure_name_code,
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

        from {{ ref("stg_google_sheets__dibels_expected_assessments") }} as e
        inner join
            {{ ref("stg_reporting__terms") }} as t
            on e.academic_year = t.academic_year
            and e.region = t.region
            and e.admin_season = t.name
            and e.test_code = t.code
            and e.assessment_type = 'PM'
            and t.type = 'LIT'
        left join
            pm_round_days as d
            on t.academic_year = d.academic_year
            and t.region = d.region
            and t.name = d.name
            and e.`round` = d.`round`
        left join
            {{ ref("stg_google_sheets__dibels_goals_long") }} as g
            on e.expected_measure_standard = g.measure_standard
            and e.grade = g.grade_level
            and e.admin_season = g.matching_pm_season
        where e.academic_year >= 2024
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="final",
                partition_by="academic_year, region, grade, admin_season, round, expected_measure_standard, pm_round_days",
            )
        }}
    )

select *
from deduplicate
