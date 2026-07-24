with
    calendar_week as (
        select
            schoolid,
            region,
            academic_year,
            week_start_monday,
            week_end_sunday,
            school_week_start_date,
            school_week_end_date,
            first_day_school_year,
            last_day_school_year,
            `quarter`,

            format_date('%G-W%V', week_start_monday) as week_label,
        from {{ ref("int_powerschool__calendar_week") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    school_weeks as (
        select
            schoolid,
            region,
            academic_year,

            'week' as period_type,

            week_label as period_label,
            week_start_monday as period_start,
            week_end_sunday as period_end,
        from calendar_week
    ),

    school_months as (
        select
            schoolid,
            region,
            academic_year,

            'month' as period_type,

            format_date('%B', month_start) as period_label,
            month_start as period_start,
            last_day(month_start, month) as period_end,
        from calendar_week
        cross join
            unnest(
                generate_date_array(
                    date_trunc(first_day_school_year, month),
                    last_day_school_year,
                    interval 1 month
                )
            ) as month_start
        group by schoolid, region, academic_year, month_start
    ),

    school_quarters as (
        select
            rt.school_id as schoolid,
            rt.city as region,
            rt.academic_year,

            'quarter' as period_type,

            rt.name as period_label,
            rt.start_date as period_start,
            rt.end_date as period_end,
        from {{ ref("stg_google_sheets__reporting__terms") }} as rt
        where
            rt.type = 'RT'
            and rt.academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    school_ytd as (
        select
            schoolid,
            region,
            academic_year,

            'ytd' as period_type,
            'YTD' as period_label,

            min(school_week_start_date) as period_start,
            max(last_day_school_year) as period_end,
        from calendar_week
        group by schoolid, region, academic_year
    ),

    school_scope as (
        select *
        from school_weeks

        union all

        select *
        from school_months

        union all

        select *
        from school_quarters

        union all

        select *
        from school_ytd
    ),

    region_scope as (
        select
            cast(null as int) as schoolid,

            region,
            academic_year,
            period_type,
            period_label,

            min(period_start) as period_start,
            max(period_end) as period_end,
        from school_scope
        group by region, academic_year, period_type, period_label
    ),

    org_scope as (
        select
            cast(null as int) as schoolid,

            'All' as region,

            academic_year,
            period_type,
            period_label,

            min(period_start) as period_start,
            max(period_end) as period_end,
        from school_scope
        group by academic_year, period_type, period_label
    ),

    /* central-office staff normalize to region TAF (dim_regions.name) but
       have no school calendar — alias the network-wide org windows */
    taf_scope as (
        select
            cast(null as int) as schoolid,

            'TAF' as region,

            academic_year,
            period_type,
            period_label,

            min(period_start) as period_start,
            max(period_end) as period_end,
        from school_scope
        group by academic_year, period_type, period_label
    ),

    all_scopes as (
        select
            schoolid,
            region,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,

            'school' as org_scope,

            cast(schoolid as string) as scope_key,
        from school_scope

        union all

        select
            schoolid,
            region,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,

            'region' as org_scope,

            region as scope_key,
        from region_scope

        union all

        select
            schoolid,
            region,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,

            'region' as org_scope,

            region as scope_key,
        from taf_scope

        union all

        select
            schoolid,
            region,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,

            'org' as org_scope,

            region as scope_key,
        from org_scope
    ),

    flagged as (
        select
            *,

            if(
                current_date('{{ var("local_timezone") }}')
                between period_start and period_end,
                true,
                false
            ) as is_current_period,

            max(
                if(
                    period_end < current_date('{{ var("local_timezone") }}'),
                    period_end,
                    null
                )
            ) over (partition by org_scope, scope_key, academic_year, period_type)
            as max_complete_period_end,
        from all_scopes
    )

select
    schoolid,
    region,
    academic_year,
    period_type,
    period_label,
    period_start,
    period_end,
    org_scope,
    scope_key,
    is_current_period,

    if(
        period_end < current_date('{{ var("local_timezone") }}')
        and period_end = max_complete_period_end
        and academic_year = {{ var("current_academic_year") }},
        true,
        false
    ) as is_most_recent_complete_period,
from flagged
