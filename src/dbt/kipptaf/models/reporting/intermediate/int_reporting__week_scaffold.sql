with
    ps_calendar as (
        select
            _dbt_source_relation,
            schoolid,
            date_value,
            membershipvalue,
            insession,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="date_value", start_month=7, year_source="start"
                )
            }} as academic_year,
            date_sub(
                safe_cast(date_value as date),
                interval extract(dayofweek from safe_cast(date_value as date)) - 2 day
            ) as week_start_monday,
            date_add(
                safe_cast(date_value as date),
                interval 8 - extract(dayofweek from safe_cast(date_value as date)) day
            ) as week_end_sunday,
        from {{ ref("stg_powerschool__calendar_day") }}
        where schoolid not in (999999, 12345, 0)
    )

select distinct
    c.academic_year,
    c.schoolid,
    c.week_start_monday,
    c.week_end_sunday,
    count(
        distinct if(c.membershipvalue = 1 and c.insession = 1, c.date_value, null)
    ) as days_in_session,
    min(t.name) as term,
from ps_calendar as c
inner join
    {{ ref("stg_reporting__terms") }} as t
    on c.academic_year = t.academic_year
    and c.schoolid = t.school_id
    and c.date_value between t.start_date and t.end_date
    and t.type = 'RT'
group by c.academic_year, c.schoolid, c.week_start_monday, c.week_end_sunday
