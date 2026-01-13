with
    weekly_spine as (
        select
            week_start as week_start_monday,
            date_add(week_start, interval 6 day) as week_end_sunday,

        from
            -- TODO: hardcoded because idk what dates SRE will ask for
            unnest(
                generate_date_array(
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc('2025-07-01', week(monday)),
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc('2026-06-30', week(monday)),
                    interval 7 day
                )
            ) as week_start
    )

select
    m._dbt_source_relation,
    m.finalsite_student_id,
    m.academic_year,
    m.academic_year_display,
    m.enrollment_year,
    m.region,
    m.schoolid,
    m.school,
    m.powerschool_student_number,
    m.last_name,
    m.first_name,
    m.grade_level,
    m.grade_level_string,
    m.detailed_status,
    m.status_start_date,
    m.status_end_date,
    m.days_in_status,
    m.enrollment_type,
    m.overall_status,
    m.funnel_status,
    m.status_category,
    m.offered_status,
    m.offered_status_detailed,
    m.detailed_status_ranking,
    m.detailed_status_branched_ranking,
    m.powerschool_enroll_status,
    m.valid_detailed_status,
    m.applicant_ops,
    m.offered_ops,
    m.pending_offer_ops,
    m.overall_conversion_ops,
    m.offers_to_accepted_den,
    m.offers_to_accepted_num,
    m.accepted_to_enrolled_den,
    m.accepted_to_enrolled_num,
    m.offers_to_enrolled_den,
    m.offers_to_enrolled_num,
    m.waitlisted,

    w.week_start_monday,
    w.week_end_sunday,

    any_value(m.detailed_status) over (
        partition by m.academic_year, m.finalsite_student_id
        order by m.status_start_date desc
    ) as latest_status,

from {{ ref("int_students__finalsite_student_roster") }} as m
inner join
    weekly_spine as w
    on m.status_start_date between w.week_start_monday and w.week_end_sunday
