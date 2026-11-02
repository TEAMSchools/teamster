with
    gpa_bands as (
        select
            label,
            min_gpa,
            points,

            coalesce(
                lead(min_gpa) over (order by min_gpa), cast('inf' as float64)
            ) as max_gpa,
        from {{ ref("stg_google_sheets__kfwd__career_launch_gpa_bands") }}
    )

select
    c.id as contact_id,
    c.current_college_cumulative_gpa,

    b.label as gpa_band,

    coalesce(b.points, 0) as gpa_points,

    if(
        p.postsec_completed_status = 'Graduated',
        p.postsec_completed_adjusted_6_year_minority_graduation_rate,
        null
    ) as ecc,
from {{ ref("stg_kippadb__contact") }} as c
left join
    gpa_bands as b
    on c.current_college_cumulative_gpa >= b.min_gpa
    and c.current_college_cumulative_gpa < b.max_gpa
left join {{ ref("int_kippadb__enrollment_pivot") }} as p on c.id = p.student
