with
    scaffold as (
        select
            b.academic_year as powerschool_academic_year,
            b.org,
            b.region,
            b.schoolid,
            b.school,
            b.grade_level,

            x.enrollment_academic_year,
            x.enrollment_academic_year_display,
            x.enrollment_type,
            x.overall_status,
            x.funnel_status,
            x.status_category,
            x.offered_status,
            x.offered_status_detailed,
            x.detailed_status_ranking,
            x.detailed_status_branched_ranking,
            x.detailed_status,
            x.valid_detailed_status,
            x.powerschool_enroll_status,
            x.sre_academic_year_start,
            x.sre_academic_year_end,

            calendar_day,

            -- trunk-ignore(sqlfluff/LT01)
            date_trunc(calendar_day, week(monday)) as sre_academic_year_wk_start_monday,

            date_add(
                -- trunk-ignore(sqlfluff/LT01)
                date_trunc(calendar_day, week(monday)), interval 6 day
            ) as sre_academic_year_wk_end_sunday,

        from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as b
        inner join
            {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} as x
            on b.academic_year = x.enrollment_academic_year
        cross join
            unnest(
                generate_date_array(
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(x.sre_academic_year_start, week(monday)),
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(x.sre_academic_year_end, week(monday)),
                    interval 1 day
                )
            ) as calendar_day
    )

select
    f._dbt_source_relation,
    f.enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.org,
    f.region,
    f.schoolid,
    f.school,
    f.grade_level,
    f.sre_academic_year_start,
    f.sre_academic_year_end,
    f.sre_academic_year_wk_start_monday,
    f.sre_academic_year_wk_end_sunday,
    f.enrollment_type,
    f.overall_status,
    f.funnel_status,
    f.status_category,
    f.offered_status,
    f.offered_status_detailed,
    f.detailed_status,
    f.detailed_status_ranking,
    f.detailed_status_branched_ranking,
    f.powerschool_enroll_status,
    f.valid_detailed_status,
    f.calendar_day,

    s.finalsite_student_id,
    s.student_finalsite_student_id,
    s.student_region,
    s.student_latest_region,
    s.student_schoolid,
    s.student_latest_schoolid,
    s.student_school,
    s.student_latest_school,
    s.student_last_name,
    s.student_first_name,
    s.student_grade_level,
    s.student_detailed_status,
    s.status_start_date,
    s.status_end_date,
    s.days_in_status,
    s.student_enrollment_year_enrollment_type,

    first_value(s.student_detailed_status) over (
        partition by s.enrollment_academic_year, s.finalsite_student_id
        order by s.status_start_date desc
    ) as latest_status,

from scaffold as f
left join
    `grangel.int_tableau__finalsite_student_scaffold` as s
    on f.enrollment_academic_year = s.enrollment_academic_year
    and f.schoolid = s.student_schoolid
    and f.detailed_status = s.detailed_status
    and f.grade_level = s.student_grade_level
    and f.calendar_day = s.calendar_day
