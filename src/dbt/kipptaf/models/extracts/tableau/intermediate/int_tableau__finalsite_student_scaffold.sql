with
    xwalk as (
        select
            r.enrollment_academic_year,
            r.enrollment_academic_year_display,
            r.sre_academic_year_start,
            r.sre_academic_year_end,
            r.org,
            r.region,
            r.finalsite_student_id,
            r.grade_level,
            r.enrollment_year_enrollment_type,

            x.overall_status,
            x.funnel_status,
            x.status_category,
            x.offered_status,
            x.offered_status_detailed,
            x.detailed_status_ranking,
            x.detailed_status_branched_ranking,
            x.detailed_status,

            calendar_day,
            -- trunk-ignore(sqlfluff/LT01)
            date_trunc(calendar_day, week(monday)) as sre_academic_year_wk_start_monday,

            date_add(
                -- trunk-ignore(sqlfluff/LT01)
                date_trunc(calendar_day, week(monday)), interval 6 day
            ) as sre_academic_year_wk_end_sunday,

        from {{ ref("int_students__finalsite_student_roster") }} as r
        inner join
            {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
            on r.enrollment_academic_year = x.enrollment_academic_year
            and r.enrollment_year_enrollment_type = x.enrollment_type
        cross join
            unnest(
                generate_date_array(
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(r.sre_academic_year_start, week(monday)),
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(r.sre_academic_year_end, week(monday)),
                    interval 1 day
                )
            ) as calendar_day
    )

select
    x.*,

    r.org as student_org,
    r.region as student_region,
    r.latest_region as student_latest_region,
    r.schoolid as student_schoolid,
    r.latest_schoolid as student_latest_schoolid,
    r.school as student_school,
    r.latest_school as student_latest_school,
    r.finalsite_student_id as student_finalsite_student_id,
    r.last_name as student_last_name,
    r.first_name as student_first_name,
    r.grade_level as student_grade_level,
    r.enrollment_year_enrollment_type as student_enrollment_year_enrollment_type,
    r.detailed_status as student_detailed_status,
    r.status_start_date,
    r.status_end_date,
    r.days_in_status,
    r.student_applicant_ops,
    r.student_offered_ops,
    r.student_pending_offer_ops,
    r.student_overall_conversion_ops,
    r.student_offers_to_accepted_num,
    r.student_offers_to_accepted_den,
    r.student_accepted_to_enrolled_num,
    r.student_accepted_to_enrolled_den,
    r.student_offers_to_enrolled_num,
    r.student_offers_to_enrolled_den,

    row_number() over (
        partition by
            x.enrollment_academic_year,
            x.finalsite_student_id,
            x.sre_academic_year_wk_start_monday
        order by x.calendar_day desc
    ) as weekly_scaffold,

from xwalk as x
left join
    {{ ref("int_students__finalsite_student_roster") }} as r
    on x.enrollment_academic_year = r.enrollment_academic_year
    and x.finalsite_student_id = r.finalsite_student_id
    and x.detailed_status = r.detailed_status
    and x.calendar_day between r.status_start_date and r.status_end_date
