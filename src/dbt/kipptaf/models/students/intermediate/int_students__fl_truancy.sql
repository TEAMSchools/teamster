{% set academic_year = var("current_academic_year") %}
{% set start_date = 'cast("' ~ academic_year ~ '-07-01" as date)' %}
{% set end_date = 'cast("' ~ (academic_year + 1) ~ '-06-30" as date)' %}

with
    date_spine as (
        {{
            dbt_utils.date_spine(
                datepart="day", start_date=start_date, end_date=end_date
            )
        }}
    ),

    truancy_lookback as (
        select
            cast(date_day as date) as date_day,
            cast(
                if(
                    date_sub(date_day, interval 90 day)
                    < date({{ var("current_academic_year") }}, 7, 1),
                    date({{ var("current_academic_year") }}, 7, 1),
                    date_sub(date_day, interval 90 day)
                ) as date
            ) as truancy_lookback
        from date_spine
    )

select
    att.academic_year,
    att.student_number,

    tl.date_day,
    tl.truancy_lookback,

    if(sum(att.is_absent) >= 15, true, false) as is_truant,
from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as att
inner join
    truancy_lookback as tl
    on att.calendardate between tl.truancy_lookback and tl.date_day
group by att.academic_year, att.student_number, tl.date_day, tl.truancy_lookback
