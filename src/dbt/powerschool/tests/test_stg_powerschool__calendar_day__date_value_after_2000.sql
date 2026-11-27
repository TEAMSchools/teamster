-- depends_on: {{ ref("stg_powerschool__calendar_day") }}
-- reads the raw source: the staging model filters these rows out
with
    calendar_day as (
        select
            cast(schoolid as int) as schoolid, cast(date_value as date) as date_value,
        from {{ source("powerschool_dlt", "calendar_day") }}
    )

select schoolid, date_value,
from calendar_day
where date_value < '2000-01-01'
