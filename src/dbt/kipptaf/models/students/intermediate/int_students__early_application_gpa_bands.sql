with
    bounded as (
        select
            gpa_band,
            band_sort,
            summary_group,

            -- a blank min_gpa marks the no-GPA band; -1 sits below every real
            -- GPA, and the rollup gives seniors with no GPA the same -1
            coalesce(min_gpa, -1) as lower_gpa,
        from {{ ref("stg_google_sheets__kfwd__early_apps_gpa_bands") }}
    ),

    next_bound as (
        select
            gpa_band,
            band_sort,
            summary_group,
            lower_gpa,

            lead(lower_gpa) over (order by lower_gpa) as next_lower_gpa,
            min(band_sort) over (partition by summary_group) as summary_sort,
        from bounded
    )

select
    gpa_band,
    band_sort,
    summary_group,
    summary_sort,
    lower_gpa,

    -- the top band has no next band; 99 is above every real GPA
    coalesce(next_lower_gpa, 99) as upper_gpa,
from next_bound
