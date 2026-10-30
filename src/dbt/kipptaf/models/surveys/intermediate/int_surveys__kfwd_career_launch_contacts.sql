with
    contacts as (
        select
            id as contact_id,
            current_college_cumulative_gpa,

            round(current_college_cumulative_gpa, 2) as gpa_rounded,
        from {{ ref("stg_kippadb__contact") }}
    ),

    college_gpa_records as (
        select
            g.student as contact_id,
            g.`source`,
            g.transcript_date,
            g.last_modified_date,

            round(g.gpa, 2) as gpa_rounded,
        from {{ ref("stg_kippadb__gpa") }} as g
        inner join
            {{ ref("stg_kippadb__record_type") }} as rt on g.record_type_id = rt.id
        where rt.name = 'Cumulative College'
    ),

    gpa_sources as (
        select
            c.contact_id,

            r.`source`,

            row_number() over (
                partition by c.contact_id
                order by r.transcript_date desc, r.last_modified_date desc
            ) as rn_source,
        from contacts as c
        inner join
            college_gpa_records as r
            on c.contact_id = r.contact_id
            and c.gpa_rounded = r.gpa_rounded
    ),

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
    c.contact_id,
    c.current_college_cumulative_gpa,

    s.`source` as current_college_cumulative_gpa_source,

    b.label as gpa_band,

    coalesce(b.points, 0) as gpa_points,

    if(
        p.postsec_completed_status = 'Graduated',
        p.postsec_completed_adjusted_6_year_minority_graduation_rate,
        null
    ) as ecc,
from contacts as c
left join gpa_sources as s on c.contact_id = s.contact_id and s.rn_source = 1
left join
    gpa_bands as b
    on c.current_college_cumulative_gpa >= b.min_gpa
    and c.current_college_cumulative_gpa < b.max_gpa
left join {{ ref("int_kippadb__enrollment_pivot") }} as p on c.contact_id = p.student
