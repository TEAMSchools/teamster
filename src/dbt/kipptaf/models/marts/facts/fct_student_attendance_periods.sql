with
    daily as (
        select
            ada.student_number,
            ada._dbt_source_project,
            ada.academic_year,
            ada.calendardate,
            ada.week_start_monday,
            ada.membershipvalue,
            ada.attendancevalue,
            ada.is_truant,

            sch.location_key,

            date(ada.academic_year, 7, 1) as year_start_date,
        from {{ ref("int_students__attendance_daily") }} as ada
        inner join
            {{ ref("int_students__schools") }} as sch
            on ada.schoolid = sch.school_number
            and ada._dbt_source_project = sch._dbt_source_project
        where ada.calendardate <= current_date('{{ var("local_timezone") }}')
    ),

    spine as (
        select
            d.*,
            period_type,
            case
                period_type
                when 'year'
                then d.year_start_date
                when 'month'
                then date_trunc(d.calendardate, month)
                when 'week'
                then d.week_start_monday
            end as period_start_date_key,
        from daily as d
        cross join unnest(['year', 'month', 'week']) as period_type
        with
        offset as period_offset
    ),

    per_period as (
        select
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,
            period_type,
            period_start_date_key,

            max(if(membershipvalue = 1, calendardate, null)) as period_end_date_key,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    membershipvalue,
                    0
                )
            ) as n_membership_days_period,

            sum(
                if(
                    membershipvalue = 1 and attendancevalue is not null,
                    attendancevalue,
                    0
                )
            ) as n_present_days_period,

            array_agg(
                if(membershipvalue = 1, is_truant, null) ignore nulls
                order by calendardate desc
                limit 1
            )[safe_offset(0)] as is_truant,
        from spine
        group by
            location_key,
            student_number,
            _dbt_source_project,
            academic_year,
            period_type,
            period_start_date_key
        having max(if(membershipvalue = 1, calendardate, null)) is not null
    ),

    aggregated as (
        select
            * except (n_membership_days_period, n_present_days_period),

            sum(n_membership_days_period) over (
                partition by
                    location_key,
                    student_number,
                    _dbt_source_project,
                    academic_year,
                    period_type
                order by period_start_date_key asc
                rows between unbounded preceding and current row
            ) as n_membership_days_ytd,

            sum(n_present_days_period) over (
                partition by
                    location_key,
                    student_number,
                    _dbt_source_project,
                    academic_year,
                    period_type
                order by period_start_date_key asc
                rows between unbounded preceding and current row
            ) as n_present_days_ytd,
        from per_period
    ),

    -- ada_tier must be a real column of a prior CTE before is_chronically_absent
    -- can be derived from it -- a select cannot reference its own alias.
    tiered as (
        select
            *,

            n_membership_days_ytd >= 10 as is_ca_eligible,

            -- n_membership_days_ytd = 0 guard is load-bearing: without it,
            -- 0 >= 0 makes a zero-membership enrollment Tier 3.
            case
                when n_membership_days_ytd = 0
                then null
                when n_present_days_ytd * 100 >= n_membership_days_ytd * 95
                then 'Tier 1'
                when n_present_days_ytd * 10 > n_membership_days_ytd * 9
                then 'Tier 2'
                when n_present_days_ytd * 10 >= n_membership_days_ytd * 8
                then 'Tier 3'
                else 'Tier 4'
            end as ada_tier,
        from aggregated
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "student_number",
                "_dbt_source_project",
                "location_key",
                "period_type",
                "period_start_date_key",
            ]
        )
    }} as student_attendance_period_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    location_key,
    academic_year,
    period_type,
    period_start_date_key,
    period_end_date_key,
    n_membership_days_ytd,
    n_present_days_ytd,
    is_truant,
    is_ca_eligible,
    ada_tier,

    ada_tier in ('Tier 3', 'Tier 4') as is_chronically_absent,
from tiered
