with
    flagged_years as (
        select distinct academic_year,
        from {{ ref("rpt_tableau__gpa_cumulative_year") }}
        where is_latest_graded_year
    )

select count(*) as n_flagged_years,
from flagged_years
having count(*) != 1
