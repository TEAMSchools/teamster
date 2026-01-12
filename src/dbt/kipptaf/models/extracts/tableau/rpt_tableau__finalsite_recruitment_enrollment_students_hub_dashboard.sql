with
    finalsite_report as (
        select
            f.* except (school),

            x.region,
            x.powerschool_school_id as schoolid,
            x.abbreviation as school,

            cast(f.academic_year as string)
            || '-'
            || right(cast(f.academic_year + 1 as string), 2) as academic_year_display,

        from {{ ref("stg_google_sheets__finalsite__sample_data") }} as f
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on f.school = x.name
    ),

    enrollment_type_calc as (
        select
            academic_year,
            student_number,
            student_first_name,
            student_last_name,

            case
                when
                    coalesce(
                        lag(
                            sum(if(date_diff(exitdate, entrydate, day) >= 7, 1, 0))
                        ) over (partition by student_number order by academic_year),
                        0
                    )
                    = 0
                then 'New'
                when
                    coalesce(
                        lag(
                            sum(if(date_diff(exitdate, entrydate, day) >= 7, 1, 0))
                        ) over (partition by student_number order by academic_year),
                        0
                    )
                    = 1
                    and academic_year - coalesce(
                        lag(academic_year) over (
                            partition by student_number order by academic_year
                        ),
                        0
                    )
                    > 1
                then 'New'
                else 'Returner'
            end as enrollment_type,

        from {{ ref("int_extracts__student_enrollments") }}
        where grade_level != 99
        group by academic_year, student_number, student_first_name, student_last_name
    ),

    mod_enrollment_type as (
        select
            f._dbt_source_relation,
            f.finalsite_student_id,
            f.academic_year,
            f.academic_year_display,
            f.enrollment_year,
            f.region,
            f.schoolid,
            f.school,
            f.powerschool_student_number,
            f.last_name,
            f.first_name,
            f.grade_level,
            f.grade_level_string,
            f.detailed_status,
            f.status_start_date,
            f.status_end_date,
            f.days_in_status,

            coalesce(e.enrollment_type, 'New') as enrollment_type,

        from finalsite_report as f
        left join
            enrollment_type_calc as e on f.powerschool_student_number = e.student_number
    ),

    weekly_spine as (
        select
            week_start as week_start_monday,
            date_add(week_start, interval 6 day) as week_end_sunday,

        from
            -- TODO: hardcoded because idk what dates SRE will ask for
            unnest(
                generate_date_array(
                    date_trunc(date '2025-09-01', week(monday)),
                    date_trunc(date '2026-08-31', week(monday)),
                    interval 7 day
                )
            ) as week_start
    )

select
    m.*,

    w.week_start_monday,
    w.week_end_sunday,

    c.overall_status,
    c.funnel_status,
    c.status_category,
    c.offered_status,
    c.offered_status_detailed,
    c.detailed_status_ranking,
    c.detailed_status_branched_ranking,
    c.powerschool_enroll_status,
    c.valid_detailed_status,

    c.applicant_ops,
    c.offered_ops,
    c.pending_offer_ops,
    c.overall_conversion_ops,
    c.offers_to_accepted_den,
    c.offers_to_accepted_num,
    c.accepted_to_enrolled_den,
    c.accepted_to_enrolled_num,
    c.offers_to_enrolled_den,
    c.offers_to_enrolled_num,
    c.waitlisted,

from mod_enrollment_type as m
inner join
    weekly_spine as w
    on m.status_start_date between w.week_start_monday and w.week_end_sunday
left join
    {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as c
    on m.academic_year = c.academic_year
    and m.enrollment_type = c.enrollment_type
    and m.detailed_status = c.detailed_status
