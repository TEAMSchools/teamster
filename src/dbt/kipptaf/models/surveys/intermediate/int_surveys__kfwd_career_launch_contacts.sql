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
    ),

    contacts as (
        select
            c.contact_id,
            c.contact_current_college_cumulative_gpa as current_college_cumulative_gpa,

            if(
                co.advisor_name is not null or ca.advisor_name is not null, true, false
            ) as is_on_caseload,

            if(
                c.contact_opt_out_national_contact
                or c.contact_opt_out_regional_contact,
                true,
                false
            ) as is_opted_out,

            -- 4 to 6 years past high school graduation
            if(
                c.contact_kipp_hs_class
                between {{ var("current_academic_year") }}
                - 5 and {{ var("current_academic_year") }}
                - 3,
                true,
                false
            ) as is_cohort_years_4_to_6,

            -- KIPP NYC is the Collab's advising provider
            if(
                c.contact_kipp_hs_class = {{ var("current_academic_year") }}
                and c.contact_advising_provider is distinct from 'KIPP NYC',
                true,
                false
            ) as is_newest_class_outside_collab,
        from {{ ref("base_kippadb__contact") }} as c
        left join
            {{ ref("stg_google_sheets__kfwd__career_launch_caseloads") }} as co
            on c.contact_owner_name = co.advisor_name
        left join
            {{ ref("stg_google_sheets__kfwd__career_launch_caseloads") }} as ca
            on c.contact_postsec_advisor_name = ca.advisor_name
    )

select
    c.contact_id,
    c.current_college_cumulative_gpa,
    c.is_on_caseload,
    c.is_cohort_years_4_to_6,
    c.is_newest_class_outside_collab,
    c.is_opted_out,

    b.label as gpa_band,

    coalesce(b.points, 0) as gpa_points,

    if(
        p.postsec_completed_status = 'Graduated',
        p.postsec_completed_adjusted_6_year_minority_graduation_rate,
        null
    ) as ecc,

    if(
        (
            c.is_on_caseload
            or c.is_cohort_years_4_to_6
            or c.is_newest_class_outside_collab
        )
        and not c.is_opted_out,
        true,
        false
    ) as is_career_launch_active,
from contacts as c
left join
    gpa_bands as b
    on c.current_college_cumulative_gpa >= b.min_gpa
    and c.current_college_cumulative_gpa < b.max_gpa
left join {{ ref("int_kippadb__enrollment_pivot") }} as p on c.contact_id = p.student
