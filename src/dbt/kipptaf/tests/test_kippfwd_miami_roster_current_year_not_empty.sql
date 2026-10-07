with
    current_year_rows as (
        select count(*) as n,
        from {{ ref("rpt_gsheets__kippfwd_miami_roster") }}
        where academic_year = {{ var("current_academic_year") }}
    )

select n,
from current_year_rows
where n = 0
