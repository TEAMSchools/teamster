with
    source as (
        select *
        from {{ ref("rpt_tableau__fresh_dashboard_aggregated") }}
    )

select
    academic_year,
    org,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    goal_type,
    goal_name,
    enrollment_type,
    grouped_status_timeframe,

    concat(
        cast(academic_year as string),
        '-',
        right(cast(academic_year + 1 as string), 2)
    ) as academic_year_display,

    min(goal_value) as goal_value,

    if(
        goal_type in ('Applications', 'Offers', 'Pending Offers'),
        min(goal_value),
        null
    ) as goal_value_counts,

    if(
        goal_type in ('Conversion', 'Assigned School'),
        min(goal_value) * 100,
        null
    ) as goal_value_pct,

    case
        when goal_type in ('Applications', 'Offers', 'Pending Offers')
            then cast(min(goal_value) as string)
        when goal_type in ('Conversion', 'Assigned School')
            then concat(cast(min(goal_value) * 100 as string), '%')
    end as display_goal,

    count(distinct goal_name_value) as goal_name_value_counts,

    safe_divide(
        count(distinct goal_name_value), count(distinct finalsite_id)
    ) as goal_name_value_pct,

    case
        when goal_type in ('Conversion', 'Assigned School')
            then concat(
                cast(
                    round(
                        safe_divide(
                            count(distinct goal_name_value),
                            count(distinct finalsite_id)
                        ) * 100,
                        1
                    ) as string
                ),
                '%'
            )
        else cast(count(distinct goal_name_value) as string)
    end as display_value,

    case
        when min(goal_value) is null
            then 'No Goal'
        when
            goal_type in ('Applications', 'Offers', 'Pending Offers')
            and count(distinct goal_name_value)
            >= min(
                case
                    when goal_type in ('Applications', 'Offers', 'Pending Offers')
                        then goal_value
                end
            )
            then 'Met Goal'
        when
            goal_type in ('Conversion', 'Assigned School')
            and safe_divide(
                count(distinct goal_name_value), count(distinct finalsite_id)
            )
            >= min(
                case
                    when goal_type in ('Conversion', 'Assigned School')
                        then goal_value
                end
            )
            then 'Met Goal'
        else 'Did Not Meet Goal'
    end as met_goal,

from source
group by
    academic_year,
    org,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    goal_type,
    goal_name,
    enrollment_type,
    grouped_status_timeframe,
