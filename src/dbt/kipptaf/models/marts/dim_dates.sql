select
    date_day,

    -- trunk-ignore(sqlfluff/LT01)
    date_trunc(date_day, week(monday)) as week_start_monday,

    -- trunk-ignore(sqlfluff/LT01)
    last_day(date_day, week(monday)) as week_end_sunday,

    {{ date_to_fiscal_year(date_field="date_day", start_month=7, year_source="start") }}
    as academic_year,
from
    unnest(
        generate_date_array('2002-07-01', '{{ var("current_fiscal_year" ) }}-06-30')
    ) as date_day
