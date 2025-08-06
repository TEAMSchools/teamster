select date_day,
from
    unnest(
        generate_date_array('2002-07-01', '{{ var("current_fiscal_year" ) }}-06-30')
    ) as date_day
