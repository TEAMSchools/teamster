with
    plans as (
        select
            intervention_plan_id,
            student_number,
            intervention_name,
            intervention_subject_area,
            district,
            school_id,
            intervention_start_date,
            intervention_end_date,

            coalesce(
                intervention_end_date, current_date('{{ var("local_timezone") }}')
            ) as end_date_or_today,
        from {{ ref("stg_branchingminds__intervention_plans") }}
        where
            intervention_start_date is not null
            and student_number is not null
            and intervention_name is not null
    ),

    plan_year_bounds as (
        select
            *,

            {{
                date_to_fiscal_year(
                    date_field="intervention_start_date",
                    start_month=7,
                    year_source="start",
                )
            }} as start_academic_year,

            {{
                date_to_fiscal_year(
                    date_field="end_date_or_today",
                    start_month=7,
                    year_source="start",
                )
            }} as end_academic_year,

            {{ current_school_year(var("local_timezone")) }} as current_academic_year,
        from plans
    ),

    plan_year_span as (
        select
            *,

            -- rows stop at the current school year; a later year's row appears
            -- once that year starts
            least(
                greatest(end_academic_year, start_academic_year), current_academic_year
            ) as last_academic_year,
        from plan_year_bounds
    ),

    plan_years as (
        select
            pyb.intervention_plan_id,
            pyb.student_number,
            pyb.intervention_name,
            pyb.intervention_subject_area,
            pyb.district,
            pyb.school_id,
            pyb.intervention_start_date,

            academic_year,

            greatest(
                pyb.intervention_start_date, date(academic_year, 7, 1)
            ) as year_start,

            case
                when pyb.intervention_end_date is not null
                then least(pyb.intervention_end_date, date(academic_year + 1, 6, 30))
                when academic_year < pyb.end_academic_year
                then date(academic_year + 1, 6, 30)
            end as year_end,
        from plan_year_span as pyb
        cross join
            unnest(
                generate_array(pyb.start_academic_year, pyb.last_academic_year)
            ) as academic_year
    ),

    plan_years_sentinel as (
        select
            *,

            -- open-ended plan: sorts last and keeps the episode open
            coalesce(year_end, cast('9999-12-31' as date)) as year_end_or_max,
        from plan_years
    ),

    plan_years_effective as (
        select
            *,

            -- a plan that ends before it starts still reaches its start date
            greatest(year_start, year_end_or_max) as year_end_effective,
        from plan_years_sentinel
    ),

    plans_ranked as (
        select
            *,

            max(year_end_effective) over (
                partition by student_number, intervention_name, academic_year
                order by year_start, year_end_or_max, intervention_plan_id
                rows between unbounded preceding and 1 preceding
            ) as prior_max_end,
        from plan_years_effective
    ),

    plans_flagged as (
        select
            *,

            -- a plan starting the day after the running end still continues it
            if(
                prior_max_end is null or date_diff(year_start, prior_max_end, day) > 1,
                1,
                0
            ) as is_new_episode,
        from plans_ranked
    ),

    plans_numbered as (
        select
            *,

            sum(is_new_episode) over (
                partition by student_number, intervention_name, academic_year
                order by year_start, year_end_or_max, intervention_plan_id
                rows between unbounded preceding and current row
            ) as episode_number,
        from plans_flagged
    ),

    plans_latest as (
        select
            *,

            row_number() over (
                partition by
                    student_number, intervention_name, academic_year, episode_number
                order by intervention_start_date desc, intervention_plan_id desc
            ) as rn_latest,
        from plans_numbered
    ),

    episodes as (
        select
            student_number,
            intervention_name,
            academic_year,
            episode_number,

            min(year_start) as episode_start,
            max(year_end_or_max) as episode_end_or_max,
            count(*) as plans_in_episode,
            array_agg(
                intervention_plan_id order by intervention_plan_id
            ) as intervention_plan_ids,
            max(
                if(rn_latest = 1, intervention_subject_area, null)
            ) as intervention_subject_area,
            max(if(rn_latest = 1, district, null)) as district,
            max(if(rn_latest = 1, school_id, null)) as school_id,
        from plans_latest
        group by student_number, intervention_name, academic_year, episode_number
    )

select
    student_number,
    intervention_name,
    academic_year,
    episode_start,
    intervention_subject_area,
    district,
    school_id,
    plans_in_episode,
    intervention_plan_ids,

    if(
        episode_end_or_max = cast('9999-12-31' as date), null, episode_end_or_max
    ) as episode_end,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "intervention_name",
                "academic_year",
                "episode_start",
            ]
        )
    }} as intervention_episode_key,

    current_date('{{ var("local_timezone") }}') >= episode_start
    and current_date('{{ var("local_timezone") }}') <= episode_end_or_max as is_current,
from episodes
